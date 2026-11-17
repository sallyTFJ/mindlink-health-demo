let id=1;
Page({
  data:{input:'',messages:[{id:id++,role:'bot',text:'我看过你今天的趋势了：整体稳定，下午专注度有一段下降。你想先聊数据原因，还是今天的感受？'}]},
  onInput(e){this.setData({input:e.detail.value});},
  quickAsk(e){this.sendText(e.currentTarget.dataset.text);},
  send(){this.sendText(this.data.input);},
  sendText(text){if(!text.trim())return;const messages=[...this.data.messages,{id:id++,role:'user',text:text.trim()}];this.setData({messages,input:''});setTimeout(()=>{const emotional=/焦虑|难受|压力/.test(text);const reply=emotional?'谢谢你告诉我。我们先不急着解决所有事：现在的紧绷感如果从 0 到 10 打分，大概是多少？先慢慢呼气 6 秒、吸气 4 秒，做 5 轮。':'演示趋势显示，下午的变化与连续久坐同步，更像认知负荷累积，不等同于疾病信号。先离开屏幕 5–10 分钟，补水并走动，是今天最小的有效行动。';this.setData({messages:[...this.data.messages,{id:id++,role:'bot',text:reply}]});},350);}
});
