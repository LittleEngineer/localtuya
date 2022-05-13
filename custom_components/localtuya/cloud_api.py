"""Class to perform requests to Tuya Cloud APIs."""
import functools
import hashlib
import hmac
import json
import requests
import sys
import time


# Signature algorithm.
def calc_sign(msg,key):
  sign = hmac.new(msg=bytes(msg, 'latin-1'),key = bytes(key, 'latin-1'), digestmod = hashlib.sha256).hexdigest().upper()
  return sign


class TuyaCloudApi:
    """Class to send API calls."""

    def __init__(self, hass, region_code, client_id, secret, user_id):
        """Initialize the class."""
        self._hass = hass
        self._base_url = f'https://openapi.tuya{region_code}.com'
        self._access_token = ""
        self._client_id = client_id
        self._secret = secret
        self._user_id = user_id

    def generate_payload(self, method, t, url, headers, body = None):
        payload = self._client_id + self._access_token + t

        payload += (method + '\n' + 
            hashlib.sha256(bytes((body or "").encode('utf-8'))).hexdigest() + '\n' + # Content-SHA256
            ''.join(
                   ['%s:%s\n'%(key, headers[key])                                   # Headers
                   for key in headers.get("Signature-Headers", "").split(":")
                   if key in headers]
                ) + 
            '\n/' + url.split('//', 1)[-1].split('/', 1)[-1])                          # Url (extracted from 'url')
        # print("PAYLOAD: {}".format(payload))
        return payload
    
    async def async_make_request(self, method, url, body=None, headers={}):
        """Perform requests."""
        t = str(int(time.time()*1000))
        payload = self.generate_payload(method, t, url, headers, body) 
        default_par={
            'client_id':self._client_id,
            'access_token':self._access_token,
            'sign':calc_sign(payload, self._secret),
            't':t,
            'sign_method':'HMAC-SHA256',  
            }
        full_url = self._base_url + url
        print("\n" + method + ": [{}]".format(full_url))

        if method == "GET":
            func = functools.partial(requests.get, full_url, headers=dict(default_par,**headers))
        elif method == "POST":
            func = functools.partial(requests.post, full_url, headers=dict(default_par,**headers), data=json.dumps(body))
            print("BODY: [{}]".format(body))
        elif method == "PUT":
            func = functools.partial(requests.put, full_url, headers=dict(default_par,**headers), data=json.dumps(body))
        
        r = await self._hass.async_add_executor_job(func)
      
        #r = json.dumps(r.json(), indent=2, ensure_ascii=False) # Beautify the request result format for easy printing and viewing
        return r

    async def async_get_access_token(self):
        """Obtain a valid access token."""
        r = await self.async_make_request("GET", f'/v1.0/token?grant_type=1')
        
        if not r.ok:
            print("Request failed, status {}".format(r.status))
            return "Request failed, status " + str(r.status)

        r_json = r.json()
        if not r_json['success']:
            print("Request failed, reply is {}".format(json.dumps(r_json, indent=2, ensure_ascii=False)))
            return f"Error {r_json['code']}: {r_json['msg']}"

        print(r.json())
        self._access_token = r.json()['result']['access_token']
        print("GET_ACCESS_TOKEN: {}".format(self._access_token))
        return "ok"
        
    async def async_get_devices_list(self):
        """Obtain the list of devices associated to a user."""
        r = await self.async_make_request("GET", url=f'/v1.0/users/{self._user_id}/devices')
        
        if not r.ok:
            print("Request failed, status {}".format(r.status))
            return None

        r_json = r.json()
        if not r_json['success']:
            print("Request failed, reply is {}".format(json.dumps(r_json, indent=2, ensure_ascii=False)))
            return None

        return r
    

