# L01S Water PI - Annotated Instruction List

Version V002; instruction count 176; source SHA256 238e10886e2d8ed4e8d2d66e758a18afe4e403f6c613f306d7859796b8ec3a88.

## 01. First-scan safe initialization. External controls are defaulted only here.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 1 | LD | M8002 |  |
 | 2 | RST | M0 |  |
 | 3 | RST | M10 |  |
 | 4 | RST | M11 |  |
 | 5 | RST | M12 |  |
 | 6 | RST | M3 |  |
 | 7 | RST | T0 |  |
 | 8 | RST | T1 |  |
 | 9 | MOV | K1 D190 |  |
 | 10 | MOV | K0 D191 |  |
 | 11 | MOV | K0 D192 |  |
 | 12 | MOV | K0 D193 |  |
 | 13 | MOV | K0 D194 |  |
 | 14 | MOV | K0 D195 |  |
 | 15 | MOV | K0 D198 |  |
 | 16 | MOV | K0 D199 |  |
 | 17 | SET | M8196 |  |
 | 18 | SET | M8125 |  |
 | 19 | MOV | HE081 D8120 |  |
 | 20 | MOV | K1 D8121 |  |
 | 21 | LD | M8002 |  |
 | 22 | AND< | D261 K10 |  |
 | 23 | MOV | K60 D261 |  |
 | 24 | LD | M8002 |  |
 | 25 | AND> | D261 K160 |  |
 | 26 | MOV | K60 D261 |  |
 | 27 | LD | M8002 |  |
 | 28 | MOV | D261 D102 |  |
 | 29 | LD | M8002 |  |
 | 30 | MOV | K2 D196 |  |
 | 31 | MOV | K31 D197 |  |
 | 32 | MOV | K28642 D200 |  |
 | 33 | MOV | K27104 D201 |  |
 | 34 | MOV | K2 D202 |  |

## 02. Unconditional global clock edge, diagnostics, and previous normal state.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 35 | LD | M8012 |  |
 | 36 | ANI | M3 |  |
 | 37 | OUT | M2 |  |
 | 38 | LD | M8012 |  |
 | 39 | OUT | M3 |  |
 | 40 | LD | M2 |  |
 | 41 | ADD | D198 K1 D198 |  |
 | 42 | LD | M8000 |  |
 | 43 | ADD | D199 K1 D199 |  |
 | 44 | MOV | D194 D195 |  |
 | 45 | LD | M0 |  |
 | 46 | ANI | M10 |  |
 | 47 | ANI | M11 |  |
 | 48 | OUT | M20 |  |

## 03. Validate and clamp the active setting without saving online edits.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 49 | LD | M8000 |  |
 | 50 | AND< | D102 K10 |  |
 | 51 | MOV | K10 D102 |  |
 | 52 | LD | M8000 |  |
 | 53 | AND> | D102 K160 |  |
 | 54 | MOV | K160 D102 |  |
 | 55 | LD | M8000 |  |
 | 56 | SUB | D102 K2 D260 |  |
 | 57 | MUL | D102 K85 D114 |  |
 | 58 | DIV | D114 K100 D116 |  |
 | 59 | MOV | D116 D262 |  |

## 04. Select signed input, clamp before scaling, and ignore unused AI channels.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 60 | LD | M8000 |  |
 | 61 | MOV | K0 D110 |  |
 | 62 | AND= | D190 K1 |  |
 | 63 | MOV | D1056 D110 |  |
 | 64 | LD | M8000 |  |
 | 65 | AND= | D190 K0 |  |
 | 66 | MOV | D8030 D110 |  |
 | 67 | LD | M8000 |  |
 | 68 | AND< | D110 K0 |  |
 | 69 | MOV | K0 D110 |  |
 | 70 | LD | M8000 |  |
 | 71 | AND> | D110 K4000 |  |
 | 72 | MOV | K4000 D110 |  |
 | 73 | LD | M8000 |  |
 | 74 | ADD | D110 K12 D111 |  |
 | 75 | DIV | D111 K25 D112 |  |
 | 76 | MOV | D112 D100 |  |

## 05. Only modes zero and one are valid. Invalid mode latches restart inhibit.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 77 | LD | M8000 |  |
 | 78 | AND= | D190 K0 |  |
 | 79 | OUT | M1 |  |
 | 80 | LD | M8000 |  |
 | 81 | AND= | D190 K1 |  |
 | 82 | OR | M1 |  |
 | 83 | OUT | M1 |  |
 | 84 | LDI | M1 |  |
 | 85 | SET | M12 |  |
 | 86 | RST | M0 |  |
 | 87 | LD | M1 |  |
 | 88 | AND= | D191 K0 |  |
 | 89 | RST | M12 |  |
 | 90 | LD | M1 |  |
 | 91 | ANI | M12 |  |
 | 92 | AND= | D191 K1 |  |
 | 93 | SET | M0 |  |
 | 94 | LD | M8000 |  |
 | 95 | AND= | D192 K1 |  |
 | 96 | RST | M0 |  |

## 06. Stop clears both states before timers and output mapping in this scan.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 97 | LDI | M0 |  |
 | 98 | RST | M10 |  |
 | 99 | RST | M11 |  |

## 07. Continuous low-pressure wake timer. False rung resets its elapsed value.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 100 | LD | M0 |  |
 | 101 | AND | M11 |  |
 | 102 | AND<= | D100 D262 |  |
 | 103 | OUT | T1 K30 |  |
 | 104 | LD | T1 |  |
 | 105 | RST | M11 |  |

## 08. Pre-sleep threshold is inclusive; each interruption resets T0 completely.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 106 | LD | M0 |  |
 | 107 | ANI | M11 |  |
 | 108 | AND>= | D100 D260 |  |
 | 109 | OUT | M10 |  |
 | 110 | LD | M10 |  |
 | 111 | OUT | T0 K50 |  |
 | 112 | LD | T0 |  |
 | 113 | SET | M11 |  |
 | 114 | RST | M10 |  |

## 09. Identify the final normal state, clear non-normal integral and safe outputs.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 115 | LD | M0 |  |
 | 116 | ANI | M10 |  |
 | 117 | ANI | M11 |  |
 | 118 | OUT | M21 |  |
 | 119 | LDI | M21 |  |
 | 120 | MOV | K0 D120 |  |
 | 121 | LDI | M0 |  |
 | 122 | OR | M11 |  |
 | 123 | MOV | K0 D154 |  |
 | 124 | LD | M10 |  |
 | 125 | MOV | K2000 D154 |  |
 | 126 | LD | M21 |  |
 | 127 | ANI | M20 |  |
 | 128 | MOV | K0 D120 |  |
 | 129 | MOV | K2000 D154 |  |

## 10. Portable integer PI, exactly once per global edge after transition scan.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 130 | LD | M21 |  |
 | 131 | AND | M20 |  |
 | 132 | AND | M2 |  |
 | 133 | SUB | D102 D100 D121 |  |
 | 134 | ADD | D120 D121 D120 |  |
 | 135 | LD | M21 |  |
 | 136 | AND | M20 |  |
 | 137 | AND | M2 |  |
 | 138 | AND< | D120 K0 |  |
 | 139 | MOV | K0 D120 |  |
 | 140 | LD | M21 |  |
 | 141 | AND | M20 |  |
 | 142 | AND | M2 |  |
 | 143 | AND> | D120 K30000 |  |
 | 144 | MOV | K30000 D120 |  |
 | 145 | LD | M21 |  |
 | 146 | AND | M20 |  |
 | 147 | AND | M2 |  |
 | 148 | MUL | D121 K10 D122 |  |
 | 149 | DIV | D120 K10 D124 |  |
 | 150 | ADD | D122 D124 D126 |  |
 | 151 | LD | M21 |  |
 | 152 | AND | M20 |  |
 | 153 | AND | M2 |  |
 | 154 | AND< | D126 K0 |  |
 | 155 | MOV | K0 D126 |  |
 | 156 | LD | M21 |  |
 | 157 | AND | M20 |  |
 | 158 | AND | M2 |  |
 | 159 | AND> | D126 K3000 |  |
 | 160 | MOV | K3000 D126 |  |
 | 161 | LD | M21 |  |
 | 162 | AND | M20 |  |
 | 163 | AND | M2 |  |
 | 164 | ADD | K2000 D126 D154 |  |

## 11. Physical route defaults OFF on every scan; exact enable value one only.

 | Step | Instruction | Operands | Comment |
 | --- | --- | --- | --- |
 | 165 | LD | M8000 |  |
 | 166 | MOV | K0 D8050 |  |
 | 167 | MOV | K0 D8051 |  |
 | 168 | LD | M0 |  |
 | 169 | AND= | D193 K1 |  |
 | 170 | AND> | D154 K0 |  |
 | 171 | OUT | Y0 |  |
 | 172 | LD | Y0 |  |
 | 173 | MUL | D154 K4 D130 |  |
 | 174 | DIV | D130 K5 D132 |  |
 | 175 | MOV | D132 D8050 |  |
 | 176 | END |  |  |

