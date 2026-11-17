App({
  globalData: {
    demo: true,
    latest: { heartRate: 72, calm: 68, sync: 82, sleep: '7h 32m', steps: 8642 }
  },
  onLaunch() {
    const consent = wx.getStorageSync('mindlink-demo-consent');
    if (!consent) wx.setStorageSync('mindlink-demo-consent', 'local-only');
  }
});
