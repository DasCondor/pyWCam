'use strict';
(() => {
 const select=document.getElementById('theme'); if(!select)return;
 let theme='system'; try{theme=localStorage.getItem('pywcam.theme')||'system';}catch{}
 const apply=value=>{if(!['system','light','dark'].includes(value))value='system';document.documentElement.dataset.theme=value;select.value=value;};
 apply(theme);select.addEventListener('change',()=>{apply(select.value);try{localStorage.setItem('pywcam.theme',select.value);}catch{}});
})();
