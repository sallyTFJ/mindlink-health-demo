const app = getApp();
Page({
  data: {...app.globalData.latest, live:false, timer:null},
  onPullDownRefresh(){ this.tick(); setTimeout(()=>wx.stopPullDownRefresh(),350); },
  onUnload(){ if(this.data.timer) clearInterval(this.data.timer); },
  toggleLive(){
    if(this.data.live){ clearInterval(this.data.timer); this.setData({live:false,timer:null}); wx.showToast({title:'实时流已暂停',icon:'none'}); return; }
    const timer=setInterval(()=>this.tick(),1200); this.setData({live:true,timer}); this.tick(); wx.showToast({title:'合成设备流已连接',icon:'success'});
  },
  tick(){ const heart=Math.max(64,Math.min(86,this.data.heartRate+Math.round((Math.random()-.5)*4))); const calm=Math.max(52,Math.min(84,this.data.calm+Math.round((Math.random()-.5)*5))); this.setData({heartRate:heart,calm,sync:Math.round((calm*.45)+(100-Math.abs(heart-71)*2)*.37+16)}); },
  goAgent(){wx.navigateTo({url:'/pages/agent/agent'});},
  goReports(){wx.navigateTo({url:'/pages/reports/reports'});}
});
