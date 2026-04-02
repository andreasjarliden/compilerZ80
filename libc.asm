puts:
	; Let IX be frame-pointer
	push	IX
	ld	IX, 0
	add	IX, SP
	; Reserve space for local variables
	ld	HL, 0fffeh
	add	HL, SP
	ld	SP, HL
	; Function content
	ld	d, (ix + 5)
	ld	e, (ix + 4)
;  ld de, str
  call BLOCKING_SEND
puts_exit:
	;Restore stack pointer (free local variables)
	ld	SP, IX
	;Restore previous frame pointer IX and return
	pop	IX
	ret


printHex8:
	; Let IX be frame-pointer
	push	IX
	ld	IX, 0
	add	IX, SP
	; Reserve space for local variables
	ld	HL, 0fffeh
	add	HL, SP
	ld	SP, HL
	; Function content
	ld	a, (ix + 5)
  call PRINT_HEX
printHex8_exit:
	;Restore stack pointer (free local variables)
	ld	SP, IX
	;Restore previous frame pointer IX and return
	pop	IX
	ret

printHex16:
	; Let IX be frame-pointer
	push	IX
	ld	IX, 0
	add	IX, SP
	; Reserve space for local variables
	ld	HL, 0fffeh
	add	HL, SP
	ld	SP, HL
	; Function content
	ld	a, (ix + 5)
  call PRINT_HEX
	ld	a, (ix + 4)
  call PRINT_HEX
printHex16_exit:
	;Restore stack pointer (free local variables)
	ld	SP, IX
	;Restore previous frame pointer IX and return
	pop	IX
	ret

