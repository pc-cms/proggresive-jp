export function physicalDigit(e) {
  if (/^Numpad[0-9]$/.test(e.code)) return Number(e.code.slice(-1));
  if (/^Digit[0-9]$/.test(e.code)) return Number(e.code.slice(-1));
  return null;
}
export function action(e, mapping={claim:'NumpadMultiply',settings:'F2',mode:'F4'}) {
  if (e.repeat || e.ctrlKey || e.altKey || e.metaKey || ['INPUT','TEXTAREA','SELECT'].includes(e.target?.tagName) || e.target?.isContentEditable) return null;
  const digit=physicalDigit(e);
  if (digit!==null) return {type:'digit',value:digit};
  if (['Enter','NumpadEnter'].includes(e.code)) return {type:'enter'};
  if (['Escape','Backspace'].includes(e.code)) return {type:'cancel'};
  for (const [type,code] of Object.entries(mapping)) if(e.code===code) return {type};
  return null;
}

// No new NumPad assignment is enabled without an operator's explicit choice.
export function reloadKey(mapping) {
  const code=mapping.reload;
  return code==='NumpadDivide'&&![mapping.claim,mapping.settings,mapping.mode].includes(code)?code:null;
}
