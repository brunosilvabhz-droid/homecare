export const states=['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];
export const professions=[
  ['nurse','Enfermeiro(a)'],['nursing_technician','Técnico(a) de enfermagem'],['caregiver','Cuidador(a)'],
  ['physiotherapist','Fisioterapeuta'],['occupational_therapist','Terapeuta ocupacional'],['speech_therapist','Fonoaudiólogo(a)'],
  ['nutritionist','Nutricionista'],['psychologist','Psicólogo(a)'],['social_worker','Assistente social'],['physician','Médico(a)'],
  ['dentist','Dentista'],['other','Outra profissão']
] as const;
export const professionCouncil:Record<string,string>={nurse:'COREN',nursing_technician:'COREN',physiotherapist:'CREFITO',occupational_therapist:'CREFITO',speech_therapist:'CREFONO',nutritionist:'CRN',psychologist:'CRP',social_worker:'CRESS',physician:'CRM',dentist:'CRO'};
