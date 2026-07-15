import {FormEvent,useEffect,useState} from 'react';
import {HeartHandshake} from 'lucide-react';
import {useNavigate,useSearchParams} from 'react-router-dom';
import {api,post} from './api';
import {professionCouncil,professions,states} from './formOptions';

const value=(form:FormData,name:string)=>String(form.get(name)||'').trim()||null;
const Input=({name,label,type='text',required=false,minLength}:{name:string;label:string;type?:string;required?:boolean;minLength?:number})=><label className="block"><span className="label">{label}</span><input className="input" name={name} type={type} required={required} minLength={minLength}/></label>;

export function AccountAuth({mode}:{mode:'login'|'register'}){
  const nav=useNavigate(); const [error,setError]=useState(''); const [success,setSuccess]=useState(''); const [profession,setProfession]=useState('');
  const submit=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault(); setError(''); const form=new FormData(e.currentTarget);
    try{
      if(mode==='login'){
        const result=await post<{access_token:string}>('/auth/login',{email:value(form,'email'),password:value(form,'password')});
        localStorage.setItem('token',result.access_token); nav('/app'); return;
      }
      const data={name:value(form,'name'),organization_name:value(form,'organization_name'),email:value(form,'email'),password:value(form,'password'),phone:value(form,'phone'),cpf:value(form,'cpf'),profession:value(form,'profession'),profession_other:value(form,'profession_other'),council_name:value(form,'council_name'),council_code:value(form,'council_code'),council_state:value(form,'council_state'),postal_code:value(form,'postal_code'),address:value(form,'address'),address_number:value(form,'address_number'),address_complement:value(form,'address_complement'),neighborhood:value(form,'neighborhood'),city:value(form,'city'),state:value(form,'state'),accept_lgpd:form.get('lgpd')==='on'};
      const result=await post<{message:string}>('/auth/register',data); setSuccess(result.message);
    }catch(reason){setError((reason as Error).message)}
  };
  if(success)return <Page><div className="card w-full max-w-lg !p-8 text-center"><HeartHandshake className="mx-auto text-brand" size={42}/><h1 className="mt-4 text-2xl">Confira seu e-mail</h1><p className="mt-3 text-ink/60">{success}</p><a className="btn-primary mt-6 inline-flex" href="/login">Ir para o login</a></div></Page>;
  return <Page><form onSubmit={submit} className={`card w-full ${mode==='register'?'max-w-3xl':'max-w-md'} !p-8`}><a href="/" className="mb-7 flex items-center gap-2 text-xl font-bold"><HeartHandshake className="text-brand"/>Impacto Care</a><h1 className="text-2xl">{mode==='login'?'Bem-vindo de volta':'Crie sua conta profissional'}</h1><p className="mb-6 mt-2 text-sm text-ink/55">{mode==='login'?'Entre na sua conta para continuar.':'30 dias grátis, sem cartão. Confirme seu e-mail para ativar a conta.'}</p>
    {mode==='login'?<div className="space-y-4"><Input name="email" label="E-mail" type="email" required/><Input name="password" label="Senha" type="password" required/></div>:<div className="grid gap-4 md:grid-cols-2">
      <Input name="name" label="Nome completo" required minLength={3}/><Input name="cpf" label="CPF" required/><Input name="phone" label="Telefone/WhatsApp" type="tel" required/><Input name="email" label="E-mail" type="email" required/><Input name="password" label="Senha (mínimo de 8 caracteres)" type="password" required minLength={8}/><Input name="organization_name" label="Nome profissional ou do negócio" required/>
      <label className="block"><span className="label">Profissão</span><select className="input" name="profession" required value={profession} onChange={e=>setProfession(e.target.value)}><option value="">Selecione</option>{professions.map(([id,label])=><option value={id} key={id}>{label}</option>)}</select></label>
      {profession==='other'&&<Input name="profession_other" label="Informe sua profissão" required/>}
      <label className="block"><span className="label">Conselho profissional</span><input className="input bg-ink/5" name="council_name" value={professionCouncil[profession]||''} placeholder="Não se aplica" readOnly/></label><Input name="council_code" label="Número do conselho (opcional)"/><StateSelect name="council_state" label="UF do conselho (opcional)" optional/>
      <Input name="postal_code" label="CEP (opcional)"/><Input name="address" label="Logradouro (opcional)"/><Input name="address_number" label="Número (opcional)"/><Input name="address_complement" label="Complemento (opcional)"/><Input name="neighborhood" label="Bairro (opcional)"/><Input name="city" label="Cidade" required/><StateSelect name="state" label="Estado (UF)"/>
      <label className="md:col-span-2 flex gap-2 text-xs text-ink/60"><input name="lgpd" type="checkbox" required/>Li e aceito os termos e o aviso de privacidade.</label>
    </div>}
    {error&&<p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}<button className="btn-primary mt-6 w-full">{mode==='login'?'Entrar':'Criar conta e validar e-mail'}</button><p className="mt-5 text-center text-sm">{mode==='login'?'Ainda não tem conta? ':'Já tem uma conta? '}<a className="font-bold text-brand" href={mode==='login'?'/cadastro':'/login'}>{mode==='login'?'Começar agora':'Entrar'}</a></p></form></Page>;
}

export function ConfirmEmail(){
  const [params]=useSearchParams(); const [state,setState]=useState('Validando seu e-mail...'); const [ok,setOk]=useState(false);
  useEffect(()=>{const token=params.get('token'); if(!token){setState('Link de confirmação inválido.');return} api<{message:string}>(`/auth/verify-email?token=${encodeURIComponent(token)}`).then(r=>{setOk(true);setState(r.message)}).catch(e=>setState(e.message))},[params]);
  return <Page><div className="card w-full max-w-lg !p-8 text-center"><HeartHandshake className="mx-auto text-brand" size={42}/><h1 className="mt-4 text-2xl">Confirmação de e-mail</h1><p className={`mt-3 ${ok?'text-brand':'text-ink/60'}`}>{state}</p>{ok&&<a className="btn-primary mt-6 inline-flex" href="/login">Entrar no Impacto Care</a>}</div></Page>;
}

function Page({children}:{children:React.ReactNode}){return <div className="grid min-h-screen place-items-center bg-sand px-4 py-10">{children}</div>}
function StateSelect({name,label,optional=false}:{name:string;label:string;optional?:boolean}){return <label className="block"><span className="label">{label}</span><select className="input" name={name} required={!optional}><option value="">Selecione</option>{states.map(state=><option key={state}>{state}</option>)}</select></label>}
