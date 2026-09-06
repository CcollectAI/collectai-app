"""The COMPLETE new-account and password-reset journeys, end to end, vs PROD.

Run it on EC2, where the keys are:

    set -a; . /opt/collectors/.env; set +a
    python3 server/scripts/verify_auth_journeys.py

Uses a mail.tm disposable inbox and always deletes the user it creates
(docs/AUTH_AND_WEB_DEPLOY.md § "Testing the email end-to-end").

WHY THIS EXISTS. The doc had a table headed "Full chain, verified (all green)"
which was neither full nor a chain: nine HTTP calls, no `resend` row, and
nothing that followed a journey to its end. It could not have caught either of
the two things it missed —

  * a 429 on resend that the APP swallowed (the API was correct; the client
    threw the answer away, which no API-level assertion can see), and
  * whether a password reset actually ends in a working login.

So this asserts OUTCOMES, not status codes:
  - a `profiles` row really exists for a new account, with its username
  - a duplicate signup returns the empty-`identities` tell that
    app/(auth)/register.tsx depends on to say "already registered"
  - a reset ends with the NEW password working AND the OLD one refused

Last full run 2026-09-06: 14/14.
"""
import json, os, random, re, string, subprocess, sys, time

SU=os.environ["SUPABASE_URL"].rstrip("/")
ANON=os.environ.get("SUPABASE_ANON_KEY") or os.environ["EXPO_PUBLIC_SUPABASE_ANON_KEY"]
SVC=os.environ["SUPABASE_SERVICE_KEY"]
REDIR="https://sparrowcollect.com/auth/callback"
PW1="SparrowOld2026x"; PW2="SparrowNew2026y"

def http(url,method="GET",body=None,headers=None,t=45,raw=False):
    cmd=["curl","-sS","-X",method,url,"-w","\n<<%{http_code}>>","--max-time",str(t)]
    for k,v in (headers or {}).items(): cmd+=["-H",f"{k}: {v}"]
    if body is not None: cmd+=["-H","Content-Type: application/json","-d",json.dumps(body)]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=t+15); out=r.stdout; code=0
    if "<<" in out: out,_,tail=out.rpartition("\n<<"); code=int(tail.strip(">>\n") or 0)
    if raw: return code,out
    try: return code,(json.loads(out) if out.strip() else {})
    except Exception: return code,{"_raw":out[:200]}

R=[]
def rec(s,ok,d=""):
    R.append((s,ok)); print(("  PASS  " if ok else "  FAIL  ")+s+(" :: "+str(d) if d else ""))

c,doms=http("https://api.mail.tm/domains"); dom=doms["hydra:member"][0]["domain"]
addr="sparrowtest"+"".join(random.choices(string.ascii_lowercase+string.digits,k=8))+"@"+dom
uname="sp"+"".join(random.choices(string.ascii_lowercase+string.digits,k=8))
http("https://api.mail.tm/accounts","POST",{"address":addr,"password":"MailTm2026x"})
c,tk=http("https://api.mail.tm/token","POST",{"address":addr,"password":"MailTm2026x"})
MT={"Authorization":"Bearer "+tk["token"]}
AH={"apikey":ANON,"Authorization":"Bearer "+ANON}
SVH={"apikey":SVC,"Authorization":"Bearer "+SVC}
print("inbox:",addr,"\n")

def wait_msgs(n,secs=120):
    for _ in range(secs//3):
        c,m=http("https://api.mail.tm/messages",headers=MT)
        ms=m.get("hydra:member",[]) if isinstance(m,dict) else []
        if len(ms)>=n: return ms
        time.sleep(3)
    c,m=http("https://api.mail.tm/messages",headers=MT)
    return m.get("hydra:member",[]) if isinstance(m,dict) else []

def link_from(msg_id, pat=r'href="([^"]*verify[^"]*)"'):
    c,f=http("https://api.mail.tm/messages/"+msg_id,headers=MT)
    h=f.get("html"); h=h[0] if isinstance(h,list) and h else (h or "")
    m=re.search(pat,h)
    return m.group(1).replace("&amp;","&") if m else None

def follow(u):
    r=subprocess.run(["curl","-sS","-o","/dev/null","-w","%{http_code} %{redirect_url}","--max-time","30",u],
                     capture_output=True,text=True)
    code,_,red=r.stdout.partition(" "); return code,red

print("--- A. NEW ACCOUNT ---")
c,r=http(f"{SU}/auth/v1/signup?redirect_to={REDIR}","POST",
         {"email":addr,"password":PW1,"data":{"username":uname,"display_name":uname}},AH)
uid=r.get("id") or (r.get("user") or {}).get("id")
rec("signup",c==200,f"HTTP {c}")

ms=wait_msgs(1); rec("confirmation email",len(ms)>=1)
lk=link_from(ms[0]["id"]) if ms else None
code,red=follow(lk) if lk else ("-","")
rec("confirm link works",code in("301","302","303") and "access_token" in red,f"HTTP {code}")

c,r=http(f"{SU}/auth/v1/token?grant_type=password","POST",{"email":addr,"password":PW1},AH)
rec("login with the password just set",c==200,f"HTTP {c}")
tok1=r.get("access_token")

# THE GAP: is a profiles row actually there?
c,prof=http(f"{SU}/rest/v1/profiles?id=eq.{uid}&select=id,username",headers=SVH)
has=isinstance(prof,list) and len(prof)==1
rec("profiles row created for the new account",has,
    (json.dumps(prof)[:90] if not has else f"username={prof[0].get('username')}"))

# THE GAP: the tell register.tsx relies on for "already registered"
c,dup=http(f"{SU}/auth/v1/signup?redirect_to={REDIR}","POST",{"email":addr,"password":PW1},AH)
ident=(dup.get("identities") if isinstance(dup,dict) else None)
if ident is None: ident=(dup.get("user") or {}).get("identities")
rec("duplicate signup returns empty identities (the 'already registered' tell)",
    isinstance(ident,list) and len(ident)==0, f"HTTP {c} identities={ident!r}")

print("\n--- B. PASSWORD RESET, ALL THE WAY TO A NEW LOGIN ---")
time.sleep(3)
c,r=http(f"{SU}/auth/v1/recover?redirect_to={REDIR}","POST",{"email":addr},AH)
rec("POST /auth/v1/recover",c==200,f"HTTP {c}")
ms2=wait_msgs(len(ms)+1); rec("reset email delivered",len(ms2)>len(ms))

rl=link_from(ms2[0]["id"]) if ms2 else None
code,red=follow(rl) if rl else ("-","")
rec("reset link carries type=recovery",code in("301","302","303") and "type=recovery" in red,
    f"HTTP {code}")
rtok=None
m=re.search(r"access_token=([^&]+)",red or "")
if m: rtok=m.group(1)
rec("recovery access_token extracted",bool(rtok))

if rtok:
    c,r=http(f"{SU}/auth/v1/user","PUT",{"password":PW2},
             {"apikey":ANON,"Authorization":"Bearer "+rtok})
    rec("set a NEW password with the recovery token",c==200,f"HTTP {c}")

time.sleep(2)
c,r=http(f"{SU}/auth/v1/token?grant_type=password","POST",{"email":addr,"password":PW2},AH)
rec("login with the NEW password",c==200,f"HTTP {c}")
c,r=http(f"{SU}/auth/v1/token?grant_type=password","POST",{"email":addr,"password":PW1},AH)
rec("OLD password no longer works",c==400,f"HTTP {c}")

if uid:
    c,_=http(f"{SU}/auth/v1/admin/users/{uid}","DELETE",None,SVH)
    rec("cleanup",c in(200,204),f"HTTP {c}")

ok=sum(1 for _,o in R if o)
print(f"\n==== {ok}/{len(R)} PASS ====")
for s,o in R:
    if not o: print("  FAILING:",s)
