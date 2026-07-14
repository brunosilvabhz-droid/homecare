export type User={id:string;name:string;email:string;role:'professional'|'family'|'admin';organization_id:string}
export type Patient={id:string;name:string;birth_date?:string;phone?:string;address?:string;notes?:string}
export type Visit={id:string;patient_id:string;starts_at:string;duration_minutes:number;status:string;notes?:string;patient:Patient}
export type RecordItem={id:string;patient_id:string;occurred_at:string;summary:string;guidance?:string;responsible_name?:string;signature_data?:string;patient:Patient}
export type Finance={id:string;description:string;amount:string;due_date:string;paid:boolean;patient?:Patient}
