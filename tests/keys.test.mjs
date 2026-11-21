import assert from 'node:assert/strict';
import {action,physicalDigit,reloadKey} from '../web/keys.mjs';
for(let n=0;n<=9;n++){
 assert.equal(physicalDigit({code:'Numpad'+n,key:'End'}),n);
 assert.deepEqual(action({code:'Numpad'+n,key:'ArrowDown',target:{tagName:'BODY'}}),{type:'digit',value:n});
}
assert.equal(action({code:'Numpad1',repeat:true}),null);
assert.equal(action({code:'Numpad1',target:{tagName:'INPUT'}}),null);
assert.equal(action({code:'NumpadEnter',target:{tagName:'INPUT'}}),null);
assert.deepEqual(action({code:'NumpadEnter'}),{type:'enter'});
assert.deepEqual(action({code:'F8'},{claim:'F8'}),{type:'claim'});
assert.deepEqual(action({code:'F4'}),{type:'mode'});
assert.equal(action({code:'NumpadDivide'}),null);
const configured={claim:'NumpadMultiply',settings:'F2',mode:'F4',reload:'NumpadDivide'};
assert.equal(reloadKey(configured),'NumpadDivide');
assert.deepEqual(action({code:'NumpadDivide'},configured),{type:'reload'});
for(const code of ['F5','F4','F2','Numpad1','Numpad0','NumpadEnter','NumpadMultiply','NumpadDecimal','NumpadAdd'])assert.equal(reloadKey({...configured,reload:code}),null);
assert.equal(reloadKey({...configured,claim:'NumpadDivide'}),null);
for(const modifier of ['ctrlKey','altKey','metaKey'])assert.equal(action({code:'NumpadDivide',[modifier]:true},configured),null);
assert.equal(action({code:'NumpadDivide',repeat:true},configured),null);
assert.equal(action({code:'NumpadDivide',target:{tagName:'INPUT'}},configured),null);
console.log('Physical NumPad, Num Lock off, repeat/PIN/modifier guards, F4 mode and opt-in reload mapping passed.');
