import {useQuery} from '@tanstack/react-query';
import {CalendarDays,ChevronRight,ClipboardList,HeartHandshake,MapPin,Phone,UserRound} from 'lucide-react';
import {Link} from 'react-router-dom';
import {api} from './api';
import type {Patient,RecordItem,Visit} from './types';

const day=(value:string)=>new Date(value).toLocaleDateString('pt-BR',{weekday:'short',day:'2-digit',month:'short'});
const hour=(value:string)=>new Date(value).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});

export default function FamilyPortalPage(){
  const {data:patients=[],isLoading:loadingPatients}=useQuery({queryKey:['family-patients'],queryFn:()=>api<Patient[]>('/patients')});
  const {data:visits=[]}=useQuery({queryKey:['family-visits'],queryFn:()=>api<Visit[]>('/visits')});
  const {data:records=[]}=useQuery({queryKey:['family-records'],queryFn:()=>api<RecordItem[]>('/records')});
  if(loadingPatients)return <p>Carregando informações autorizadas...</p>;
  if(!patients.length)return <div className="card text-center"><HeartHandshake className="mx-auto text-brand" size={38}/><h1 className="mt-4 text-2xl">Portal da Família</h1><p className="mt-2 text-ink/55">Nenhum paciente foi vinculado a este acesso. Solicite o convite ao profissional responsável.</p></div>;
  return <section className="space-y-6">
    <header><p className="text-sm font-bold uppercase tracking-wide text-brand">Portal da Família</p><h1 className="mt-1">Acompanhamento autorizado</h1><p className="mt-1 text-ink/55">Consulte os dados do paciente, os próximos atendimentos e a linha do tempo compartilhada.</p></header>
    {patients.map(patient=>{const patientVisits=visits.filter(item=>item.patient_id===patient.id&&item.status!=='canceled'),upcoming=patientVisits.filter(item=>new Date(item.starts_at)>=new Date()),patientRecords=records.filter(item=>item.patient_id===patient.id);return <article className="space-y-5" key={patient.id}>
      <div className="card"><div className="flex items-start gap-3"><div className="avatar-initials">{patient.name.split(' ').slice(0,2).map(part=>part[0]).join('')}</div><div className="min-w-0"><h2 className="text-xl">{patient.name}</h2><div className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-sm text-ink/55">{patient.phone&&<span className="flex items-center gap-1"><Phone size={14}/>{patient.phone}</span>}{patient.city&&<span className="flex items-center gap-1"><MapPin size={14}/>{[patient.city,patient.state].filter(Boolean).join(' · ')}</span>}</div></div></div><div className="mt-5 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3"><Info label="Condições informadas" value={patient.conditions}/><Info label="Medicamentos informados" value={patient.medications}/><Info label="Necessidades de cuidado" value={patient.care_needs}/></div></div>
      <div className="grid gap-5 xl:grid-cols-[.8fr_1.2fr]">
        <div className="card"><h2 className="flex items-center gap-2 text-lg"><CalendarDays className="text-brand" size={20}/>Próximos atendimentos</h2><div className="mt-4 space-y-3">{upcoming.map(visit=><div className="rounded-xl border border-ink/10 p-3" key={visit.id}><b className="capitalize">{day(visit.starts_at)}</b><p className="mt-1 text-sm text-ink/55">{hour(visit.starts_at)} · {visit.duration_minutes} minutos</p><span className="mt-2 inline-flex rounded-full bg-mint px-2.5 py-1 text-xs font-semibold text-brand">{visit.patient_response==='confirmed'?'Confirmado':'Agendado'}</span></div>)}{!upcoming.length&&<p className="text-sm text-ink/50">Não há atendimento futuro agendado.</p>}</div></div>
        <div className="card"><h2 className="flex items-center gap-2 text-lg"><ClipboardList className="text-brand" size={20}/>Linha do tempo</h2><p className="mt-1 text-sm text-ink/50">Abra um atendimento para consultar todas as informações compartilhadas.</p><div className="mt-4 divide-y divide-ink/10">{patientRecords.map(record=><Link className="flex items-center gap-3 py-4 transition hover:text-brand" to={`/app/records/${record.id}`} key={record.id}><span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-mint text-brand"><UserRound size={18}/></span><span className="min-w-0 flex-1"><b className="block text-sm">{new Date(record.occurred_at).toLocaleString('pt-BR')}</b><span className="mt-1 block truncate text-sm text-ink/55">{record.summary}</span></span><ChevronRight size={18}/></Link>)}{!patientRecords.length&&<p className="py-5 text-sm text-ink/50">Ainda não há atendimento compartilhado.</p>}</div></div>
      </div>
    </article>})}
    <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">As informações exibidas são registros administrativos de atendimento compartilhados pelo profissional. Elas não substituem documentos clínicos oficiais nem orientações profissionais.</p>
  </section>
}

function Info({label,value}:{label:string;value?:string}){return <div className="rounded-xl bg-ink/[.035] p-3"><b className="block text-xs text-ink/55">{label}</b><p className="mt-1 break-words">{value||'Não informado'}</p></div>}
