const API=import.meta.env.VITE_API_URL||'http://localhost:8000/api/v1';
export const token=()=>localStorage.getItem('token');
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{const res=await fetch(`${API}${path}`,{...options,headers:{'Content-Type':'application/json',...(token()?{Authorization:`Bearer ${token()}`}:{}) ,...options.headers}});if(!res.ok){const e=await res.json().catch(()=>({detail:'Erro inesperado'}));const detail=typeof e.detail==='string'?e.detail:e.detail?.message;throw new Error(detail||'Erro inesperado')}return res.json()}
export const post=<T>(path:string,data:unknown)=>api<T>(path,{method:'POST',body:JSON.stringify(data)});
export const patch=<T>(path:string,data:unknown)=>api<T>(path,{method:'PATCH',body:JSON.stringify(data)});
export const put=<T>(path:string,data:unknown)=>api<T>(path,{method:'PUT',body:JSON.stringify(data)});
