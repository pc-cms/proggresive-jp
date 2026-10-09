import assert from 'node:assert/strict';
import {action,physicalDigit} from '../web/keys.mjs';
for(let n=0;n<=9;n++){
 assert.equal(physicalDigit({code:'Numpad'+n,key:'End'}),n);
 assert.deepEqual(action({code:'Numpad'+n,key:'ArrowDown',target:{tagName:'BODY'}}),{type:'digit',value:n});
}
assert.equal(action({code:'Numpad1',repeat:true}),null);
assert.equal(action({code:'Numpad1',target:{tagName:'INPUT'}}),null);
assert.equal(action({code:'NumpadEnter',target:{tagName:'INPUT'}}),null);
assert.deepEqual(action({code:'NumpadEnter'}),{type:'enter'});
assert.deepEqual(action({code:'F8'},{claim:'F8'}),{type:'claim'});
console.log('Physical NumPad codes, Num Lock off, repeat suppression, PIN input and custom mapping passed.');
