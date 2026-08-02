#ifndef __STDIO_H__
// #define __STDIO_H__

char printHex16(int n);
char printHex8(char n);
char puts(char* s);
void putchar(char c);

#include <stdarg.h>

char printHex16(int n);
char printHex8(char n);
char puts(char* s);
void putchar(char c);
char getchar();
void printf(char* fmt, ...);

#include <stdio.c>

#endif
