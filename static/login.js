'use strict';
const form = document.getElementById('login');
form.addEventListener('submit', async e => {
  e.preventDefault(); const button=form.querySelector('button'); button.disabled=true;
  const error=document.getElementById('loginError'); error.textContent='';
  try {
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json','X-PyWCam':'1'},body:JSON.stringify(Object.fromEntries(['username','password','code'].map(k=>[k,document.getElementById(k).value])))});
    if(r.ok) {location.replace('/');return;}
    error.textContent=(await r.json()).error;
  } catch {error.textContent='Sign-in unavailable.';}
  finally {button.disabled=false;document.getElementById('code').value='';document.getElementById('password').value='';}
});
