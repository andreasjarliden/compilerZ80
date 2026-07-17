#include <stddef.h>

#define containerof(ptr, st, member) \
  (st*)((char*)ptr - offsetof(st, member))

struct list_head {
  struct list_head* prev;
  struct list_head* next;
};

void init_list_head(struct list_head* n);

void __list_add(struct list_head* new,
                struct list_head* prev,
                struct list_head* next);

void list_add(struct list_head* new,
              struct list_head* head);

#include <list.c>
