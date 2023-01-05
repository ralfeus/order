  curl 'https://shop-api.atomy.com/svc/cart/addToCart?_siteId=kr&_deviceType=pc&locale=en-KR' \
  -H 'cookie: atomySvcJWT=SDP+eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJzdmMiLCJqdGkiOiJcZiRcdTAwMDcmIFx1MDAxNCQhIiwiYXVkIjoiOTQuMTEyLjMwLjE0OCwgMTMwLjE3Ni4xNDMuOTciLCJpc3MiOiJJLU9OIiwiaWF0IjoxNjcyOTE1Nzk5LCJleHAiOjMyNDcyMTExNjAwfQ.5reXcBy2xytiThYkL4S69L60FmVpO-eL3uXpwzVrsRCf1FaoRvPpNlhi8OPTGofNWO6O4kZdu_4kgbsb5mG58Q' \
  --data-raw 'cartType=BUYNOW&salesApplication=QUICK_ORDER&products=[{"product":"1856808780","quantity":1}]&cart=A33471172090277862&channel=WEB'

  curl 'https://shop-api.atomy.com/svc/cart/updateCart?_siteId=kr&_deviceType=pc&locale=en-KR' \
  -H 'cookie: atomySvcJWT=SDP+eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJzdmMiLCJqdGkiOiJcZiRcdTAwMDcmIFx1MDAxNCQhIiwiYXVkIjoiOTQuMTEyLjMwLjE0OCwgMTMwLjE3Ni4xNDMuOTciLCJpc3MiOiJJLU9OIiwiaWF0IjoxNjcyOTE1Nzk5LCJleHAiOjMyNDcyMTExNjAwfQ.5reXcBy2xytiThYkL4S69L60FmVpO-eL3uXpwzVrsRCf1FaoRvPpNlhi8OPTGofNWO6O4kZdu_4kgbsb5mG58Q' \
  --data-raw 'command=CREATE_DEFAULT_DELIVERY_INFOS&cart=A33471172090277862&cartType=BUYNOW&salesApplication=QUICK_ORDER&channel=WEB' 

  curl 'https://shop-api.atomy.com/svc/cart/updateCart?_siteId=kr&_deviceType=pc&locale=en-KR' \
  -H 'cookie: atomySvcJWT=SDP+eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJzdmMiLCJqdGkiOiJcZiRcdTAwMDcmIFx1MDAxNCQhIiwiYXVkIjoiOTQuMTEyLjMwLjE0OCwgMTMwLjE3Ni4xNDMuOTciLCJpc3MiOiJJLU9OIiwiaWF0IjoxNjcyOTE1Nzk5LCJleHAiOjMyNDcyMTExNjAwfQ.5reXcBy2xytiThYkL4S69L60FmVpO-eL3uXpwzVrsRCf1FaoRvPpNlhi8OPTGofNWO6O4kZdu_4kgbsb5mG58Q' \
  --data-raw 'command=UPDATE_PAYMENT_TYPE&cart=A33471172090277862&cartType=BUYNOW&salesApplication=QUICK_ORDER&payload={"id":"ACCOUNT_TRANSFER"}&channel=WEB'

  curl 'https://shop-api.atomy.com/svc/cart/updateCart?_siteId=kr&_deviceType=pc&locale=en-KR' \
  -H 'cookie: atomySvcJWT=SDP+eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJzdmMiLCJqdGkiOiJcZiRcdTAwMDcmIFx1MDAxNCQhIiwiYXVkIjoiOTQuMTEyLjMwLjE0OCwgMTMwLjE3Ni4xNDMuOTciLCJpc3MiOiJJLU9OIiwiaWF0IjoxNjcyOTE1Nzk5LCJleHAiOjMyNDcyMTExNjAwfQ.5reXcBy2xytiThYkL4S69L60FmVpO-eL3uXpwzVrsRCf1FaoRvPpNlhi8OPTGofNWO6O4kZdu_4kgbsb5mG58Q' \
  --data-raw $'&command=UPDATE_ORDER_USER&cart=A33471172090277862&cartType=BUYNOW&salesApplication=QUICK_ORDER&payload={"userName":"Mychajlo Chodorev","userCellphone":"01056352045","userTelephone":"","userEmail":"","salesDate":"2023-01-05"}&channel=WEB'

  curl 'https://shop-api.atomy.com/svc/cart/updateCart?_siteId=kr&_deviceType=pc&locale=en-KR' \
  -H 'cookie: atomySvcJWT=SDP+eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJzdmMiLCJqdGkiOiJcZiRcdTAwMDcmIFx1MDAxNCQhIiwiYXVkIjoiOTQuMTEyLjMwLjE0OCwgMTMwLjE3Ni4xNDMuOTciLCJpc3MiOiJJLU9OIiwiaWF0IjoxNjcyOTE1Nzk5LCJleHAiOjMyNDcyMTExNjAwfQ.5reXcBy2xytiThYkL4S69L60FmVpO-eL3uXpwzVrsRCf1FaoRvPpNlhi8OPTGofNWO6O4kZdu_4kgbsb5mG58Q' \
  --data-raw $'&command=APPLY_PAYMENT_TRANSACTION&cart=A33471172090277862&cartType=BUYNOW&salesApplication=QUICK_ORDER&payload={"paymentTransactions":[{"plannedAmount":31900,"depositDeadline":"20230106150000","phoneNumber":"01056352045","status":"AUTHORIZATION","info":{"bank":"KOOKMIN","config":"846967375"},"taxInvoice":{"type":"NONE","proofType":"DEDUCTION","numberType":"CPN","number":"01056352045"}}]}&channel=WEB'

  curl 'https://shop-api.atomy.com/svc/order/validateCheckout?_siteId=kr&_deviceType=pc&locale=en-KR' \
  -H 'cookie: atomySvcJWT=SDP+eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJzdmMiLCJqdGkiOiJcZiRcdTAwMDcmIFx1MDAxNCQhIiwiYXVkIjoiOTQuMTEyLjMwLjE0OCwgMTMwLjE3Ni4xNDMuOTciLCJpc3MiOiJJLU9OIiwiaWF0IjoxNjcyOTE1Nzk5LCJleHAiOjMyNDcyMTExNjAwfQ.5reXcBy2xytiThYkL4S69L60FmVpO-eL3uXpwzVrsRCf1FaoRvPpNlhi8OPTGofNWO6O4kZdu_4kgbsb5mG58Q' \
 --data-raw 'cartId=A33471172090277862'

  curl 'https://shop-api.atomy.com/svc/order/placeOrder?_siteId=kr&_deviceType=pc&locale=en-KR' \
  -H 'cookie: atomySvcJWT=SDP+eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJzdmMiLCJqdGkiOiJcZiRcdTAwMDcmIFx1MDAxNCQhIiwiYXVkIjoiOTQuMTEyLjMwLjE0OCwgMTMwLjE3Ni4xNDMuOTciLCJpc3MiOiJJLU9OIiwiaWF0IjoxNjcyOTE1Nzk5LCJleHAiOjMyNDcyMTExNjAwfQ.5reXcBy2xytiThYkL4S69L60FmVpO-eL3uXpwzVrsRCf1FaoRvPpNlhi8OPTGofNWO6O4kZdu_4kgbsb5mG58Q' \
  --data-raw 'cartId=A33471172090277862&customerId='