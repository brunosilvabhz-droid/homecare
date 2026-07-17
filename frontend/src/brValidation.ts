export const digits=(value:string)=>value.replace(/\D/g,'');

export function maskCpf(value:string){
  const number=digits(value).slice(0,11);
  return number.replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d{1,2})$/,'$1-$2');
}

export function maskPhone(value:string){
  const number=digits(value).replace(/^55(?=\d{10,11}$)/,'').slice(0,11);
  if(number.length<=10)return number.replace(/^(\d{2})(\d)/,'($1) $2').replace(/(\d{4})(\d)/,'$1-$2');
  return number.replace(/^(\d{2})(\d)/,'($1) $2').replace(/(\d{5})(\d)/,'$1-$2');
}

export function validCpf(value:string){
  const number=digits(value);
  if(number.length!==11||/^(\d)\1+$/.test(number))return false;
  const check=(base:string)=>{const total=[...base].reduce((sum,item,index)=>sum+Number(item)*(base.length+1-index),0);const result=11-total%11;return result>=10?'0':String(result)};
  return number.slice(-2)===check(number.slice(0,9))+check(number.slice(0,10));
}

export function validPhone(value:string,mobileOnly=false){
  const number=digits(value).replace(/^55(?=\d{10,11}$)/,'');
  return mobileOnly?/^[1-9]{2}9\d{8}$/.test(number):/^[1-9]{2}(?:9\d{8}|[2-8]\d{7})$/.test(number);
}

export function configureBrazilianInput(input:HTMLInputElement,name:string){
  if(name==='cpf'){
    input.value=maskCpf(input.value);
    input.maxLength=14;
    input.inputMode='numeric';
    input.pattern='\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2}';
    input.title='Informe um CPF válido';
  }
  if(name.includes('phone')){
    input.value=maskPhone(input.value);
    input.maxLength=15;
    input.inputMode='tel';
    input.pattern='\\([1-9]{2}\\) (?:9\\d{4}|[2-8]\\d{3})-\\d{4}';
    input.title='Informe o telefone com DDD';
  }
}
