const app = getApp()

Page({
  data: {
    cloudBaseUrl: "",
    types: ["text", "voice", "image", "link", "video_link"],
    typeIndex: 0,
    content: "",
    mediaUrl: "",
    tagsText: "",
    items: [],
    submitting: false,
    loadingStatus: false
  },

  onLoad() {
    const saved = wx.getStorageSync("cloudBaseUrl")
    this.setData({
      cloudBaseUrl: saved || app.globalData.defaultCloudBaseUrl
    })
    this.loadStatus()
  },

  onCloudBaseInput(event) {
    const value = event.detail.value
    this.setData({ cloudBaseUrl: value })
    wx.setStorageSync("cloudBaseUrl", value)
  },

  onTypeChange(event) {
    this.setData({ typeIndex: Number(event.detail.value) })
  },

  onContentInput(event) {
    this.setData({ content: event.detail.value })
  },

  onMediaUrlInput(event) {
    this.setData({ mediaUrl: event.detail.value })
  },

  onTagsInput(event) {
    this.setData({ tagsText: event.detail.value })
  },

  tags() {
    return this.data.tagsText
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  },

  submitInspiration() {
    const base = this.data.cloudBaseUrl.replace(/\/$/, "")
    if (!base) {
      wx.showToast({ title: "先填云端地址", icon: "none" })
      return
    }
    if (!this.data.content && !this.data.mediaUrl) {
      wx.showToast({ title: "内容或链接至少填一个", icon: "none" })
      return
    }
    this.setData({ submitting: true })
    wx.request({
      url: `${base}/api/mobile/inspirations`,
      method: "POST",
      data: {
        type: this.data.types[this.data.typeIndex],
        content: this.data.content,
        media_url: this.data.mediaUrl,
        tags: this.tags()
      },
      success: () => {
        wx.showToast({ title: "已提交", icon: "success" })
        this.setData({ content: "", mediaUrl: "", tagsText: "" })
        this.loadStatus()
      },
      fail: () => {
        wx.showToast({ title: "提交失败", icon: "none" })
      },
      complete: () => {
        this.setData({ submitting: false })
      }
    })
  },

  loadStatus() {
    const base = this.data.cloudBaseUrl.replace(/\/$/, "")
    if (!base) return
    this.setData({ loadingStatus: true })
    wx.request({
      url: `${base}/api/mobile/inspirations/status`,
      method: "GET",
      success: (response) => {
        const items = response.data && Array.isArray(response.data.items) ? response.data.items : []
        this.setData({ items: items.slice(-10).reverse() })
      },
      fail: () => {
        wx.showToast({ title: "状态读取失败", icon: "none" })
      },
      complete: () => {
        this.setData({ loadingStatus: false })
      }
    })
  }
})
