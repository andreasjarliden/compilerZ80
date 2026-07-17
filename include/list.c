#include "stdio.h"

void init_list_head(struct list_head* n) {
  n->prev = n;
  n->next = n;
}

void __list_add(struct list_head* new,
                struct list_head* prev,
                struct list_head* next) {
  next->prev = new;
  prev->next = new;
  new->next = next;
  new->prev = prev;
}

void list_add(struct list_head* new,
              struct list_head* head) {
  __list_add(new, head, head->next);
}
