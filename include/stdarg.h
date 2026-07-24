#define va_list void*

#define va_start(ap, last) \
  ap = (va_list)((void*)&last + sizeof(last))

#define va_arg(ap, type) \
  *(type*)((ap=ap + sizeof(type)) - sizeof(type))

#define va_end(ap) 0
