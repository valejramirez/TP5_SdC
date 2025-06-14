# Makefile para el módulo cdd_reader

# Le decimos al sistema de compilación que queremos construir un módulo
# cuyo archivo objeto se llama cdd_reader.o
obj-m := cdd_signal_reader.o

# La 'regla' por defecto que se ejecuta cuando escribes 'make'
all:
	$(MAKE) -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules

# La 'regla' que se ejecuta cuando escribes 'make clean'
clean:
	$(MAKE) -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean
