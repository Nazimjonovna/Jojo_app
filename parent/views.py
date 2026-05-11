from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from random import randint
from rest_framework import status, generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import (Userserializer, PhoneSerializer, SMSCodeSerializer, UserLoginSerializer,)
from .models import User, Validatedcode, Verification
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.parsers import MultiPartParser, FileUploadParser
from drf_yasg.utils import swagger_auto_schema
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
# from get_sms import Getsms
import datetime as d
import pytz
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import traceback



utc = pytz.timezone(settings.TIME_ZONE)
min = 1
def send_sms(phone_number, step_reset=None, change_phone=None):
    try:
        verify_code = randint(1111, 9999)
        try:
            obj = Verification.objects.get(phone=phone_number)
        except Verification.DoesNotExist:
            obj = Verification(phone=phone_number, verify_code=verify_code)
            obj.step_reset=step_reset 
            obj.step_change_phone=change_phone
            obj.save()
            context = {'phone_number': str(obj.phone), 'verify_code': obj.verify_code,
                       'lifetime': _(f"{min} minutes")}
            return context
        time_now = d.datetime.now(utc)
        diff = time_now - obj.created
        three_minute = d.timedelta(minutes=min)
        if diff <= three_minute:
            time_left = str(three_minute - diff)
            return {'message': _(f"Try again in {time_left[3:4]} minute {time_left[5:7]} seconds")}
        obj.delete()
        obj = Verification(phone=phone_number)
        obj.verify_code=verify_code 
        obj.step_reset=step_reset
        obj.step_change_phone=change_phone
        obj.save()
        context = {'phone_number': str(obj.phone), 'verify_code': obj.verify_code, 'lifetime': _(f"{min} minutes")}
        return context
    except Exception as e:
        print(f"\n[ERROR] error in send_sms <<<{e}>>>\n")



class PhoneView(APIView):
    queryset = User.objects.all()
    serializer_class = PhoneSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=PhoneSerializer, tags = ['Register'])
    def post(self, request, *args, **kwargs):
        phone_number = str(request.data.get("phone"))
        if phone_number.isdigit() and len(phone_number)>8:
            user = User.objects.filter(phone__iexact=phone_number)
            if user.exists():
                return Response({
                    "status": False,
                    "detail": "Bu raqam avval registerdan otgan."
                })
            else:
                code = send_sms(phone_number)
                if 'verify_code' in code:
                    code = str(code['verify_code'])
                    try:
                        validate = Validatedcode.objects.get(phone=phone_number)
                        if validate.validated:
                            validate.code = code
                            validate.validated= False
                            validate.save()
                        
                    except Validatedcode.DoesNotExist as e:
                        phon = Validatedcode.objects.filter(phone__iexact=phone_number)
                        print("expect")
                        if not phon.exists():
                            Validatedcode.objects.create(phone=phone_number, code=code, validated=False)
                        else:
                            Response({"phone": "mavjud"})

                return Response({
                    "status": True,
                    "detail": "SMS xabarnoma jo'natildi",
                    "code":code 
                })
        else:
            if len(phone_number)<8:
                return Response({"detail":"Telefon raqamingizni kod bilan kiriting!"})
            else:    
                return Response({
                    "status": False,
                    "detail": "Telefon raqamni kiriting ."
                })


    def send_code(phone, code):
        if phone:
            code = randint(999, 9999)
            print(code)
            return code
        else:
            return False


class codeView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=SMSCodeSerializer, tags = ['Register'])
    def post(self, request):
        phone_number = request.data.get('phone', True)
        code_send = request.data.get('code', True)
        if not phone_number and code_send:
            return Response({
                    'status': False,
                    'detail': 'codeni va phone ni kiriting'
                })

        try:
            verify = Validatedcode.objects.get(phone=phone_number, validated=False)
            if verify.code == code_send:
                    verify.count += 1
                    verify.validated = True
                    verify.save()

                    return Response({
                        'status': True,
                        'detail': "code to'g'ri"
                        })
            else:
                return Response({
                   'status': False,
                   'error': "codeni to'g'ri kiriting"})
            
        except Validatedcode.DoesNotExist as e:
            return Response({
               'error': "code aktiv emas yoki mavjud emas, boshqa code oling"
            })

        


class ValidatedcodeView(APIView):
    @swagger_auto_schema(tags=['User'])
    def post(self, request, *args, **kwargs):
        phone = request.data.get('phone', False)
        code_sent = request.data.get('code', False)

        if phone and code_sent:
            old = Validatedcode.objects.filter(phone__iexact=phone)
            if old.exists():
                old = old.first()
                code = old.code
                if str(code_sent) == str(code):
                    old.validated = True
                    old.save()   
                    return Response({
                        'status': True,
                        'detail': "code to'g'ri"
                        })
                else:
                    return Response({
                        'status': False,
                        'detail': "code noto'g'ri"
                        })
            else:
                return Response({
                    'status': False,
                    'detail': "code aktiv emas yoki mavjud emas, boshqa code oling"
                    })

@method_decorator(csrf_exempt, name='dispatch')
class RegisterUserView(generics.CreateAPIView):
    permission_classes = [AllowAny, ]
    serializer_class = Userserializer
    parser_classes = [MultiPartParser, FileUploadParser]

    @swagger_auto_schema(request_body=Userserializer, tags=['User'])
    def post(self, request):
        
        try:
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid():
                user_obj = serializer.save()
                phone = serializer.validated_data.get('phone')
                password = serializer.validated_data.get('password')
                code = serializer.validated_data.get('code')
                first_name = request.data.get('first_name')
                last_name = request.data.get('last_name')
                gender = request.data.get('gender')
                birth_date = request.data.get('birth_date')
                address = request.data.get('address')
                city = request.data.get('city')
                country = request.data.get('country')
                postal_code = request.data.get('postal_code')
                pasport = request.data.get('pasport')
                pasport_seria = request.data.get('pasport_seria')
                is_who = request.data.get('is_who')
                verify = Validatedcode.objects.filter(phone__iexact=phone, validated=True)
                if not verify.exists():
                    return Response({
                        "status": False,
                        "detail": _("You haven't entered a valid one-time secret code. Therefore, you cannot proceed with registration.")
                    }, status=status.HTTP_400_BAD_REQUEST)

                hashed_password = make_password(password)
                user_obj = User.objects.create(phone=phone, password=hashed_password, code=code, first_name=first_name,
                                               gender=gender, birth_date=birth_date, address=address, last_name = last_name,
                                               city=city, country=country, postal_code=postal_code,
                                               pasport=pasport, pasport_seria=pasport_seria, is_who=is_who)

                access_token = AccessToken().for_user(user_obj)
                refresh_token = RefreshToken().for_user(user_obj)

                return Response({
                    "access": str(access_token),
                    "refresh": str(refresh_token),
                    "phone": str(user_obj.phone),
                })
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(e)
            return Response({
                "status": False,
                "detail": _("An error occurred while processing your request.")
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)