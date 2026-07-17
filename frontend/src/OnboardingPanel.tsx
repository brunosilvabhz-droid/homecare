import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Bot,CalendarClock,Check,ChevronDown,ChevronLeft,ChevronRight,ChevronUp,FileSignature,HeartHandshake,Landmark,Users} from 'lucide-react';
import {Link} from 'react-router-dom';
import {api} from './api';

type Step={code:string;title:string;benefit:string;action_path:string;completed:boolean};
type Onboarding={steps:Step[]};

const essentialCodes=['email','profile','patient','schedule','record'];
const discoveries=[
  {title:'Configure sua disponibilidade',text:'Em Disponibilidade, escolha os dias e horários de trabalho e informe a duração média das sessões. Esses dados geram os horários livres da agenda.',path:'/app/availability',action:'Configurar horários',icon:CalendarClock},
  {title:'Cadastre sua assinatura',text:'Na mesma tela de Disponibilidade, preencha nome, profissão e conselho. A assinatura será incluída automaticamente nos registros e PDFs.',path:'/app/availability',action:'Cadastrar assinatura',icon:FileSignature},
  {title:'Use o Assistente de IA',text:'Abra um atendimento agendado e peça apoio para preparação ou evolução. A IA considera as informações permitidas e os registros anteriores.',path:'/app/ai',action:'Conhecer a IA',icon:Bot},
  {title:'Compartilhe com a família',text:'Na página do paciente, envie um acesso individual ao familiar. Ele verá somente o paciente ao qual foi vinculado.',path:'/app/patients',action:'Ver pacientes',icon:Users},
  {title:'Organize o financeiro',text:'Registre receitas e despesas por categoria, acompanhe valores pendentes e veja projeções diretamente na visão geral.',path:'/app/finance',action:'Abrir financeiro',icon:Landmark},
  {title:'Gere registros organizados',text:'Cada atendimento pode ser consultado na linha do tempo e aberto em PDF com sua assinatura profissional personalizada.',path:'/app/records',action:'Ver atendimentos',icon:HeartHandshake},
];

export default function OnboardingPanel(){
  const {data}=useQuery({queryKey:['onboarding'],queryFn:()=>api<Onboarding>('/onboarding')});
  const [collapsed,setCollapsed]=useState(false),[slide,setSlide]=useState(0);
  if(!data)return null;
  const steps=essentialCodes.map(code=>data.steps.find(step=>step.code===code)).filter((step):step is Step=>Boolean(step));
  const completed=steps.filter(step=>step.completed).length,progress=Math.round(completed/steps.length*100),next=steps.find(step=>!step.completed),discovery=discoveries[slide],Icon=discovery.icon;
  const move=(direction:number)=>setSlide(current=>(current+direction+discoveries.length)%discoveries.length);
  return <section className="card mb-5 border-brand/20 !p-4 sm:!p-5">
    <div className="flex items-center justify-between gap-4">
      <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-x-3 gap-y-1"><p className="text-xs font-bold uppercase tracking-wider text-brand">Comece por aqui</p><span className="text-xs text-ink/45">{completed}/{steps.length} etapas</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink/10"><div className="h-full rounded-full bg-brand transition-all" style={{width:`${progress}%`}}/></div></div>
      <button className="rounded-lg border border-ink/10 p-2 text-ink/60" onClick={()=>setCollapsed(value=>!value)} aria-label={collapsed?'Expandir orientações':'Recolher orientações'}>{collapsed?<ChevronDown size={18}/>:<ChevronUp size={18}/>}</button>
    </div>
    {!collapsed&&<div className="mt-4 grid gap-4 xl:grid-cols-[1.35fr_.9fr]">
      <div className="rounded-xl border border-ink/10 bg-white p-4">
        <div className="flex gap-2 overflow-x-auto pb-2">{steps.map((step,index)=><div className={`flex min-w-fit items-center gap-2 rounded-full px-3 py-2 text-xs font-semibold ${step.completed?'bg-mint text-brand':step.code===next?.code?'bg-brand text-white':'bg-ink/5 text-ink/45'}`} key={step.code}><span className={`grid h-5 w-5 place-items-center rounded-full ${step.completed?'bg-brand text-white':'bg-white/80 text-ink/60'}`}>{step.completed?<Check size={13}/>:index+1}</span>{step.title}</div>)}</div>
        {next?<div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-ink/10 pt-3"><div><b className="text-sm">Próximo passo: {next.title}</b><p className="mt-0.5 text-xs text-ink/55">{next.benefit}</p></div><Link className="btn-primary !min-h-9 !px-4 !py-2 text-sm" to={next.action_path}>Fazer agora</Link></div>:<p className="mt-3 rounded-lg bg-mint p-3 text-sm font-semibold text-brand">Trilha inicial concluída. Seu primeiro atendimento já está organizado.</p>}
      </div>
      <div className="relative rounded-xl border border-brand/15 bg-mint/35 p-4">
        <div className="flex items-start gap-3"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-brand shadow-sm"><Icon size={20}/></div><div className="pr-12"><p className="text-[11px] font-bold uppercase tracking-wide text-brand">Descubra outras funções</p><h3 className="mt-1 text-base">{discovery.title}</h3><p className="mt-1 text-xs leading-5 text-ink/60">{discovery.text}</p><Link className="mt-2 inline-flex text-xs font-bold text-brand underline" to={discovery.path}>{discovery.action} →</Link></div></div>
        <div className="absolute right-3 top-3 flex gap-1"><button className="rounded-lg bg-white p-1.5 text-ink/60 shadow-sm" onClick={()=>move(-1)} aria-label="Funcionalidade anterior"><ChevronLeft size={16}/></button><button className="rounded-lg bg-white p-1.5 text-ink/60 shadow-sm" onClick={()=>move(1)} aria-label="Próxima funcionalidade"><ChevronRight size={16}/></button></div>
        <div className="mt-3 flex justify-center gap-1.5">{discoveries.map((item,index)=><button className={`h-1.5 rounded-full transition-all ${index===slide?'w-5 bg-brand':'w-1.5 bg-brand/25'}`} key={item.title} onClick={()=>setSlide(index)} aria-label={`Ver ${item.title}`}/>)}</div>
      </div>
    </div>}
  </section>
}
