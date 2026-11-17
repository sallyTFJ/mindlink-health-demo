Page({
  data:{files:[{name:'可穿戴设备 365 天合成样例.csv',ext:'CSV',size:'46.3'}]},
  chooseFile(){wx.chooseMessageFile({count:3,type:'file',extension:['pdf','csv','json','png','jpg'],success:res=>{const incoming=res.tempFiles.map(file=>({name:file.name,ext:file.name.split('.').pop().slice(0,4).toUpperCase(),size:(file.size/1024).toFixed(1)}));this.setData({files:[...incoming,...this.data.files]});wx.showToast({title:'已本地读取',icon:'success'});},fail:()=>wx.showToast({title:'未选择文件',icon:'none'})});}
});
