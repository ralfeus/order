REM  *****  BASIC  *****

Sub Main
	length = 63
	set sheet = ThisComponent.Sheets(0)
	sheet.getCellByPosition(0, length + 1).formula = _
		"=""DELETE FROM shipping_rates WHERE destination IN ('""&TEXTJOIN(""','"";1;B1:J1)&""') AND shipping_method_id=1;"""
	for col = 1 to 9
		start = col * length 
		for row = 1 to length
			dst = sheet.getCellByPosition(col, 0).string
			weight = sheet.getCellByPosition(0, row).value * 1000
			rate = sheet.getCellByPosition(col, row).value
			if rate <> 0 then
				sheet.getCellByPosition(0, start + row + 1).string = _
					"INSERT INTO shipping_rates (destination, weight, rate, shipping_method_id) values ('" & dst & "', " & weight & ", " & rate & ", 1);"
			end if
		next
	next
End sub