export type User={id:string;name:string;email:string;role:'professional'|'family'|'admin';organization_id:string}
export type Patient={id:string;name:string;cpf?:string;birth_date?:string;gender?:string;phone?:string;email?:string;postal_code?:string;address?:string;address_number?:string;address_complement?:string;neighborhood?:string;city?:string;state?:string;notes?:string}
export type Visit={id:string;patient_id:string;starts_at:string;duration_minutes:number;status:string;notes?:string;patient:Patient}
export type RecordItem={id:string;patient_id:string;occurred_at:string;summary:string;guidance?:string;responsible_name?:string;signature_data?:string;patient:Patient}
export type Finance={id:string;description:string;amount:string;due_date:string;paid:boolean;patient?:Patient}
