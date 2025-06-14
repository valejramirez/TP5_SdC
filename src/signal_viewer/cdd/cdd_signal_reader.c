// SPDX-License-Identifier: GPL-2.0
/*
 * cdd_signal_reader.c – Stage 3 (dual-channel serial GPIO reader)
 * ---------------------------------------------------------------
 *  /dev/signal_reader  ·  ioctl select SIG1/SIG2  ·  two kfifos
 */

#include <linux/module.h>
#include <linux/init.h>
#include <linux/fs.h>
#include <linux/cdev.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio.h>
#include <linux/interrupt.h>
#include <linux/kfifo.h>
#include <linux/spinlock.h>
#include <linux/uaccess.h>
#include <linux/ioctl.h>
#include <linux/wait.h>
#include <linux/atomic.h>
#include <linux/version.h>

#define DEVICE_NAME "signal_reader"

/* BCM offsets (header 0-53) */
#define BCM_SIG1   24
#define BCM_SIG2    6
#define BCM_CLOCK  26

/* module param: first GPIO of 54-line bank */
static unsigned int base = 569;                /* Pi 5 gpiochip569 */
module_param(base, uint, 0444);
MODULE_PARM_DESC(base,
        "Global GPIO number of BCM0 (default 569 on Raspberry Pi 5)");

/* active read channel */
enum sr_channel { SR_CH_SIG1 = 0, SR_CH_SIG2 = 1 };
static atomic_t active_ch = ATOMIC_INIT(SR_CH_SIG1);

/* FIFOs, lock, wait-queue */
#define SR_FIFO_SIZE 1024
static DECLARE_KFIFO(sig1_fifo, u8, SR_FIFO_SIZE);
static DECLARE_KFIFO(sig2_fifo, u8, SR_FIFO_SIZE);
static spinlock_t fifo_lock;
static DECLARE_WAIT_QUEUE_HEAD(read_wq);

/* ioctl numbers */
#define SR_IOC_MAGIC   's'
#define SR_IOC_SET_CH  _IOW(SR_IOC_MAGIC, 0, int)   /* 0=SIG1 1=SIG2 */
#define SR_IOC_GET_CH  _IOR(SR_IOC_MAGIC, 1, int)

/* chardev / GPIO globals */
static dev_t            dev_num;
static struct cdev      sr_cdev;
static struct class    *sr_class;
static struct gpio_desc *gpiod_s1, *gpiod_s2, *gpiod_clk;
static int               clk_irq = -1;
static atomic64_t        edge_count = ATOMIC64_INIT(0);

/* helper: get descriptor, force INPUT */
static struct gpio_desc *acquire_desc(unsigned int bcm, const char *tag)
{
        struct gpio_desc *d = gpio_to_desc(base + bcm);
        if (!d) {
                pr_err("sr: gpio_to_desc(%u) %s NULL\n", base + bcm, tag);
                return NULL;
        }
        gpiod_direction_input(d);
        pr_info("sr: %s → BCM%u ↦ GPIO%u OK\n", tag, bcm, base + bcm);
        return d;
}

/* shift-register state */
static u8 shift_reg[2];
static u8 bit_pos [2];

/* IRQ: sample both SIGs, push byte each 8 edges */
static irqreturn_t clk_isr(int irq, void *d)
{
        int bit1 = gpiod_get_value(gpiod_s1);
        int bit2 = gpiod_get_value(gpiod_s2);
        unsigned long flags;

        /* SIG1 */
        shift_reg[SR_CH_SIG1] |= (bit1 & 1) << bit_pos[SR_CH_SIG1];
        if (++bit_pos[SR_CH_SIG1] == 8) {
                spin_lock_irqsave(&fifo_lock, flags);
                kfifo_in(&sig1_fifo, &shift_reg[SR_CH_SIG1], 1);
                spin_unlock_irqrestore(&fifo_lock, flags);
                shift_reg[SR_CH_SIG1] = 0;
                bit_pos [SR_CH_SIG1] = 0;
                wake_up_interruptible(&read_wq);
        }

        /* SIG2 */
        shift_reg[SR_CH_SIG2] |= (bit2 & 1) << bit_pos[SR_CH_SIG2];
        if (++bit_pos[SR_CH_SIG2] == 8) {
                spin_lock_irqsave(&fifo_lock, flags);
                kfifo_in(&sig2_fifo, &shift_reg[SR_CH_SIG2], 1);
                spin_unlock_irqrestore(&fifo_lock, flags);
                shift_reg[SR_CH_SIG2] = 0;
                bit_pos [SR_CH_SIG2] = 0;
                wake_up_interruptible(&read_wq);
        }

        atomic64_inc(&edge_count);
        return IRQ_HANDLED;
}

/* fops stubs */
static int sr_open(struct inode *ino, struct file *f)   { return 0; }
static int sr_release(struct inode *ino, struct file *f){ return 0; }

static ssize_t sr_read(struct file *f, char __user *buf,
                       size_t cnt, loff_t *off)
{
        unsigned long flags;
        unsigned int copied;
        int ret;

        if (cnt == 0)
                return 0;

        /* -------- canal SIG2 -------- */
        if (atomic_read(&active_ch) == SR_CH_SIG2) {
                if (kfifo_is_empty(&sig2_fifo)) {
                        if (f->f_flags & O_NONBLOCK)
                                return -EAGAIN;
                        if (wait_event_interruptible(read_wq,
                                                     !kfifo_is_empty(&sig2_fifo)))
                                return -ERESTARTSYS;
                }
                spin_lock_irqsave(&fifo_lock, flags);
                ret = kfifo_to_user(&sig2_fifo, buf, cnt, &copied);
                spin_unlock_irqrestore(&fifo_lock, flags);
                return ret ? ret : copied;
        }

        /* -------- canal SIG1 -------- */
        if (kfifo_is_empty(&sig1_fifo)) {
                if (f->f_flags & O_NONBLOCK)
                        return -EAGAIN;
                if (wait_event_interruptible(read_wq,
                                             !kfifo_is_empty(&sig1_fifo)))
                        return -ERESTARTSYS;
        }
        spin_lock_irqsave(&fifo_lock, flags);
        ret = kfifo_to_user(&sig1_fifo, buf, cnt, &copied);
        spin_unlock_irqrestore(&fifo_lock, flags);
        return ret ? ret : copied;
}

/* ioctl: set / get channel */
static long sr_ioctl(struct file *f, unsigned int cmd, unsigned long arg)
{
        int ch;

        switch (cmd) {
        case SR_IOC_SET_CH:
                if (get_user(ch, (int __user *)arg))
                        return -EFAULT;
                if (ch != SR_CH_SIG1 && ch != SR_CH_SIG2)
                        return -EINVAL;
                atomic_set(&active_ch, ch);
                return 0;
        case SR_IOC_GET_CH:
                ch = atomic_read(&active_ch);
                if (put_user(ch, (int __user *)arg))
                        return -EFAULT;
                return 0;
        default:
                return -ENOTTY;
        }
}

static const struct file_operations sr_fops = {
        .owner          = THIS_MODULE,
        .open           = sr_open,
        .release        = sr_release,
        .read           = sr_read,
        .unlocked_ioctl = sr_ioctl,
#if defined(CONFIG_COMPAT)
        .compat_ioctl   = sr_ioctl,
#endif
};

/* ── INIT / EXIT ─────────────────────────────────────────────────── */
static int __init sr_init(void)
{
        int ret;

        pr_info("sr: *** base=%u ***\n", base);

        if ((ret = alloc_chrdev_region(&dev_num, 0, 1, DEVICE_NAME)))
                return ret;

        cdev_init(&sr_cdev, &sr_fops);
        if ((ret = cdev_add(&sr_cdev, dev_num, 1)))
                goto err_chrdev;

#if LINUX_VERSION_CODE < KERNEL_VERSION(6,7,0)
        sr_class = class_create(THIS_MODULE, DEVICE_NAME);
#else
        sr_class = class_create(DEVICE_NAME);
#endif
        if (IS_ERR(sr_class)){ ret = PTR_ERR(sr_class); goto err_cdev; }

        if (IS_ERR(device_create(sr_class, NULL, dev_num, NULL, DEVICE_NAME))){
                ret = -ENOMEM; goto err_class; }

        /* GPIO & IRQ */
        gpiod_s1  = acquire_desc(BCM_SIG1,  "SIG1");
        gpiod_s2  = acquire_desc(BCM_SIG2,  "SIG2");
        gpiod_clk = acquire_desc(BCM_CLOCK, "CLK" );
        if (!gpiod_s1 || !gpiod_s2 || !gpiod_clk){ ret = -ENODEV; goto err_dev; }

        clk_irq = gpiod_to_irq(gpiod_clk);
        if (clk_irq < 0){ ret = clk_irq; goto err_dev; }

        ret = request_irq(clk_irq, clk_isr,
                          IRQF_TRIGGER_RISING | IRQF_NO_SUSPEND,
                          DEVICE_NAME, NULL);
        if (ret) goto err_dev;

        spin_lock_init(&fifo_lock);
        INIT_KFIFO(sig1_fifo);
        INIT_KFIFO(sig2_fifo);

        pr_info("sr: Reader ready – IRQ=%d, /dev/%s (major=%d)\n",
                clk_irq, DEVICE_NAME, MAJOR(dev_num));
        return 0;

/* rollback */
err_dev:   device_destroy(sr_class, dev_num);
err_class: class_destroy(sr_class);
err_cdev : cdev_del(&sr_cdev);
err_chrdev: unregister_chrdev_region(dev_num,1);
        return ret;
}

static void __exit sr_exit(void)
{
        if (clk_irq >= 0)
                free_irq(clk_irq, NULL);

        device_destroy(sr_class, dev_num);
        class_destroy(sr_class);
        cdev_del(&sr_cdev);
        unregister_chrdev_region(dev_num,1);
        pr_info("sr: module unloaded\n");
}

module_init(sr_init);
module_exit(sr_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("NoLoSonIEEE");
MODULE_DESCRIPTION("Dual-channel serial GPIO reader (Raspberry Pi 5)");
MODULE_IMPORT_NS(GPIOLIB);
