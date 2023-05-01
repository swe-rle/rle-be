from fastapi import Depends, HTTPException, APIRouter, Response, Request
from starlette.responses import FileResponse
from google.oauth2 import id_token
from google.auth.exceptions import InvalidValue
import jwt
import schemas, models,utils
from sqlalchemy.orm import Session
from starlette.responses import FileResponse
import datetime ,time   
from fastapi.responses import HTMLResponse
from pathlib import Path

from google.oauth2 import id_token
from google.auth.transport import requests
from utils import get_db


router = APIRouter()

# Google OAuth2 client ID
CLIENT_ID = '658208509868-eobuvr8pnb5k1knq91cq27tl794rp67l.apps.googleusercontent.com'
GSUITE_DOMAIN_NAME = "iith.ac.in"
JWT_SCERET = "68a89b238f114ec7b4dbe1d69014399ff18ec2b22f12146fd63a98faf398d80f"
COOKIE_KEY = "rle_session"

class RleSession:
    def __init__(self, user_id, name, email, role_id, person_id, role_name):
        self.userid = user_id
        self:name =  name
        self.email = email
        self.role_id = role_id
        self.person_id = person_id
        self.role_name = role_name
        self.valid = True
        
    def __init__(self, jwt_payload):
        self.__init__(jwt_payload['userid'],
                jwt_payload['name'], 
                jwt_payload['email'],
                jwt_payload['role_id'], 
                jwt_payload['person_id'], 
                jwt_payload['role_name']
                 )

    def __init__(self, reason:str):
        self.valid = False
        self.reason = reason

    def db(self):
        get_db()
    
    

# This function verifies the JWT token and returns the decoded payload
def _get_session(request: Request):
    ## Remove this to validate api
    rle_session_ck = request.cookies.get(COOKIE_KEY)
    if not rle_session_ck:
        return RleSession("No Cookie")
    try:
        decoded_token = jwt.decode(rle_session_ck, JWT_SCERET,algorithms="HS256")
        return RleSession(decoded_token)
    
    except (jwt.exceptions.InvalidTokenError, jwt.exceptions.InvalidSignatureError,ValueError, KeyError) as v:
        print(v.with_traceback())
        return RleSession("Invalid Token")
    
 

@router.get("/",response_class=HTMLResponse)
async def read_index(response: Response):
    # response.header["Referrer-Policy"]= "no-referrer-when-downgrade"
    return Path("index.html").read_text()


@router.post("/auth/signin")
async def after_sign_in(signin_data:schemas.SignInData, response:Response, db: Session = Depends(utils.get_db)):
    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(signin_data.g_token, requests.Request(), CLIENT_ID)

        # If auth request is from a G Suite domain:
        if idinfo['hd'] != GSUITE_DOMAIN_NAME:
            raise ValueError('Wrong hosted domain.')

        role_id,person_id = get_person_role_by_email(idinfo['email'],signin_data.lab_id,db);
        # ID token is valid. Get the user's Google Account ID from the decoded token.
        jwt_payload = {
            "userid" : idinfo['sub'],
            "name":idinfo['name'],
            "email":idinfo['email'],
            "role_id": role_id,
            "person_id": person_id,
            "role_name":utils.get_role_name_by_id(role_id)
            }
        # Creating a JWT and send cookie
        jwt_token = jwt.encode(jwt_payload,JWT_SCERET,algorithm="HS256")
        response.set_cookie(COOKIE_KEY, jwt_token,samesite="lax")

        return jwt_payload
    

    # except ValueError as v:
    #     # Invalid token
    #     print(v.with_traceback())

    except InvalidValue:
        return HTTPException(status_code=401, detail='Token is invalid')


@router.post("/auth/signout")
async def after_sign_in(response:Response):
    response.set_cookie(COOKIE_KEY,"",expires=time.gmtime(0))
    return {"message": "Logged out successfully"}



def get_person_role_by_email(email:str,lab_id:int,db:Session):
    # get person id from email
    person = db.query(models.Person).filter(models.Person.roll_number == email).first()
    # print(person)
    if not person:
        raise HTTPException(status_code=401, detail='User not authorized for this lab')
    lab_member = db.query(models.LabMember).filter(models.LabMember.person_id == person.id,models.LabMember.lab_id==lab_id).first()
    if not lab_member:
        raise HTTPException(status_code=401, detail='User not authorized for this lab')
    
    return lab_member.role_id,lab_member.person_id
    
