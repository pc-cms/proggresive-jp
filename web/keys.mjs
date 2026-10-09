export function physicalDigit(e) {
  if (/^Numpad[0-9]$/.test(e.code)) return Number(e.code.slice(-1));
  if (/^Digit[0-9]$/.test(e.code)) return Number(e.code.slice(-1));
  return null;
}
export function action(e, mapping={claim:'NumpadMultiply',settings:'F2',mode:'F4'}) {
  if (e.repeat || ['INPUT','TEXTAREA','SELECT'].includes(e.target?.tagName) || e.target?.isContentEditable) return null;
  const digit=physicalDigit(e);
  if (digit!==null) return {type:'digit',value:digit};
  if (['Enter','NumpadEnter'].includes(e.code)) return {type:'enter'};
  if (['Escape','Backspace'].includes(e.code)) return {type:'cancel'};
  for (const [type,code] of Object.entries(mapping)) if(e.code===code) return {type};
  return null;
}
