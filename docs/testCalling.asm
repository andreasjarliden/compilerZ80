#include "constants.asm"
  .org 8000h
  ; push arguments right to left
  ld    bc, 1
  push  bc
  ld    bc, 2
  push  bc

  call  myFunc

  ; Free the arguments from the stac
  ld    hl, 4
  add   hl, sp
  ld    sp, hl

  ; return value in A
  call  PRINT_HEX
  ret

;myFunc(int8 a, int8 b)
myFunc: 
  ; ix as frame-pointer
  push  ix
  ld    ix, 0
  add   ix, sp

  ; Reserve 1 byte
  ld    hl, 0ffffh
  add   hl, sp
  ld    sp, hl

  ; Preserve registers (except ix (already preserved) and return registers a and hl

  ; Initialize variable
  ld    (ix+0), 42h

  ; load arg1
  ld    a, (ix+4)

  ; add arg2
  add   a, (ix+6)

  ; add var1
  add   a, (ix+0)

  ; restore the stack pointer
  ld    sp, ix
  
  ; restore ix
  pop   ix
  ret

