void printf(char* fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  char c = *fmt;
  while (c != 0) {
    if (c == 37) { // %
      fmt = fmt + 1;
      c = *fmt;
      if (c == 100) { // %d
        int i = va_arg(ap, int);
        printHex16(i);
        fmt = fmt + 1;
        c = *fmt;
        continue;
      }
      // TODO error
    }
    putchar(c);
    fmt = fmt + 1;
    c = *fmt;
  }
  va_end(ap);
}

