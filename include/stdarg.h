#define va_list void*

// TODO: replace 2 with sizeof
#define va_start(ap, last) \
  ap = (va_list)((void*)&last + 2)

// TODO: replace 2 with sizeof
#define va_arg(ap, type) \
  *(type*)((ap=ap + 2) - 2)

#define va_end(ap) 0
