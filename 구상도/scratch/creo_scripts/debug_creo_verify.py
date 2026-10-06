from pathlib import Path
stage=Path.home()/'AppData/Local/Temp/creo_tunnel_20261005'
p=stage/'verify.creojs'
code=p.read_text()
code=code.replace('const results=[];','const results=[]; let phase="start"; try {')
for expr in ['session.ChangeDirectory','const model=session.RetrieveModel','const pcb=session.RetrieveModel','const outline=pcb.GeomOutline','const expected=n===6','const models=session.ListModels','const expectedModels=n+5','results.push']:
    code=code.replace(expr,'phase='+repr(expr)+'; '+expr)
code=code.replace('return results;','return {ok:true,results:results}; } catch(e) { return {ok:false,phase:phase,error:String(e),name:e.name,message:e.message,exceptionType:e.ExceptionType,results:results}; }')
p.write_text(code,encoding='utf-8')
print('Instrumented verification')
