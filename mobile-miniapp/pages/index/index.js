const app = getApp()

const QUEUE_KEY = "penmojiCaptureQueue"
const CLOUD_URL_KEY = "penmojiCloudBaseUrl"
const LINKED_DEVICE_KEY = "penmojiLinkedDeviceId"
const MOBILE_DEVICE_KEY = "penmojiMobileDeviceId"

const TYPE_DEFS = [
  { key: "text", label: "文字灵感" },
  { key: "link", label: "链接" },
  { key: "video_link", label: "视频素材" },
  { key: "image", label: "图片素材" },
  { key: "voice", label: "语音线索" }
]

const INTENT_DEFS = [
  { key: "collect", label: "只收录" },
  { key: "score", label: "先评分" },
  { key: "review", label: "先审核" },
  { key: "script", label: "写脚本" },
  { key: "publish_copy", label: "发布文案" }
]

const PRESET_TAGS = ["选题", "个人IP", "待验证", "评论区", "素材", "金句", "脚本", "抖音", "发布"]

function nowIso() {
  return new Date().toISOString()
}

function localId() {
  return `pm_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`
}

function trimUrl(url) {
  return String(url || "").trim().replace(/\/$/, "")
}

function detectUrl(text) {
  const match = String(text || "").match(/https?:\/\/[^\s]+/i)
  return match ? match[0].replace(/[，。；、,.!?]+$/, "") : ""
}

function isVideoLink(url) {
  return /douyin|iesdouyin|tiktok|bilibili|xiaohongshu|xhslink/i.test(url || "")
}

function normalizeLinkCode(value) {
  const text = String(value || "").trim()
  const match = text.match(/[?&]code=([A-Za-z0-9]+)/) || text.match(/\b([A-Za-z0-9]{6})\b/)
  return (match ? match[1] : text).replace(/[^A-Za-z0-9]/g, "").slice(0, 12).toUpperCase()
}

function statusText(status, remoteStatus) {
  const value = remoteStatus || status
  return {
    draft: "本机草稿",
    queued: "待同步",
    syncing: "同步中",
    failed: "同步失败",
    synced: "已提交",
    pending: "已提交",
    pulled: "电脑已接收",
    archived: "已进入项目",
    processed: "已生成产物"
  }[value] || "未知状态"
}

function statusTone(status, remoteStatus) {
  const value = remoteStatus || status
  if (["archived", "processed", "pulled"].includes(value)) return "done"
  if (["synced", "pending"].includes(value)) return "pending"
  if (["failed"].includes(value)) return "failed"
  return "draft"
}

function timeLabel(value) {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const month = `${date.getMonth() + 1}`.padStart(2, "0")
  const day = `${date.getDate()}`.padStart(2, "0")
  const hour = `${date.getHours()}`.padStart(2, "0")
  const minute = `${date.getMinutes()}`.padStart(2, "0")
  return `${month}-${day} ${hour}:${minute}`
}

Page({
  data: {
    cloudBaseUrl: "",
    linkCode: "",
    linkedDeviceId: "",
    bindingStatus: "尚未绑定电脑端",
    showSettings: false,
    captureTypes: [],
    captureIntents: [],
    tagOptions: [],
    currentType: "text",
    captureIntent: "collect",
    content: "",
    mediaUrl: "",
    customTag: "",
    selectedTags: [],
    customTags: [],
    localQueue: [],
    remoteItems: [],
    recentItems: [],
    summaryText: "准备收录灵感",
    summaryTone: "idle",
    retryCount: 0,
    submitting: false,
    syncingQueue: false,
    loadingStatus: false,
    binding: false,
    editingDraftId: "",
    submitButtonText: "保存并同步"
  },

  onLoad() {
    const savedUrl = wx.getStorageSync(CLOUD_URL_KEY) || wx.getStorageSync("cloudBaseUrl")
    const queue = this.readQueue()
    this.setData({
      cloudBaseUrl: savedUrl || app.globalData.defaultCloudBaseUrl,
      localQueue: queue,
      linkedDeviceId: wx.getStorageSync(LINKED_DEVICE_KEY) || "",
      bindingStatus: wx.getStorageSync(LINKED_DEVICE_KEY) ? "已绑定电脑端" : "尚未绑定电脑端"
    })
    this.refreshOptions()
    this.refreshRecent()
    this.loadStatus({ quiet: true })
    this.syncQueue({ quiet: true })
  },

  readQueue() {
    const queue = wx.getStorageSync(QUEUE_KEY)
    if (!Array.isArray(queue)) return []
    return queue.map((item) => ({
      ...item,
      status: item.status === "syncing" ? "queued" : item.status || "draft"
    }))
  },

  writeQueue(queue) {
    wx.setStorageSync(QUEUE_KEY, queue)
    this.setData({ localQueue: queue })
    this.refreshRecent()
  },

  refreshOptions() {
    this.setData({
      captureTypes: TYPE_DEFS.map((item) => ({ ...item, active: item.key === this.data.currentType })),
      captureIntents: INTENT_DEFS.map((item) => ({ ...item, active: item.key === this.data.captureIntent })),
      tagOptions: PRESET_TAGS.map((label) => ({ label, active: this.data.selectedTags.includes(label) }))
    })
  },

  toggleSettings() {
    this.setData({ showSettings: !this.data.showSettings })
  },

  onCloudBaseInput(event) {
    const value = event.detail.value
    this.setData({ cloudBaseUrl: value })
    wx.setStorageSync(CLOUD_URL_KEY, value)
  },

  onLinkCodeInput(event) {
    this.setData({ linkCode: normalizeLinkCode(event.detail.value) })
  },

  mobileDeviceId() {
    let id = wx.getStorageSync(MOBILE_DEVICE_KEY)
    if (!id) {
      id = localId()
      wx.setStorageSync(MOBILE_DEVICE_KEY, id)
    }
    return id
  },

  scanDeviceCode() {
    wx.scanCode({
      onlyFromCamera: false,
      success: (result) => {
        this.setData({ linkCode: normalizeLinkCode(result.result) })
      },
      fail: () => {
        wx.showToast({ title: "扫码取消或失败", icon: "none" })
      }
    })
  },

  bindDeviceCode() {
    const base = trimUrl(this.data.cloudBaseUrl)
    const code = normalizeLinkCode(this.data.linkCode)
    if (!base) {
      wx.showToast({ title: "先填写同步地址", icon: "none" })
      return
    }
    if (!code) {
      wx.showToast({ title: "先输入设备码", icon: "none" })
      return
    }
    this.setData({ binding: true, bindingStatus: "正在绑定电脑端..." })
    wx.request({
      url: `${base}/api/device/link`,
      method: "POST",
      data: {
        code,
        mobile_device_id: this.mobileDeviceId(),
        mobile_device_name: "penmoji-miniapp"
      },
      success: (response) => {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          const error = response.data && response.data.error ? response.data.error : ""
          const message = {
            "device code not found": "设备码不存在，请检查后重试",
            "device code expired": "设备码已过期，请在电脑端重新生成"
          }[error] || "设备码不可用"
          this.setData({ bindingStatus: message })
          return
        }
        const link = response.data && response.data.link ? response.data.link : {}
        const deviceId = response.data.desktop_device_id || link.desktop_device_id || ""
        if (deviceId) {
          wx.setStorageSync(LINKED_DEVICE_KEY, deviceId)
          this.setData({ linkedDeviceId: deviceId, bindingStatus: `已绑定电脑端：${deviceId.slice(0, 8)}` })
          wx.showToast({ title: "绑定成功", icon: "success" })
        } else {
          this.setData({ bindingStatus: "云端未返回设备 ID" })
        }
      },
      fail: () => {
        this.setData({ bindingStatus: "绑定失败，检查同步地址或网络" })
      },
      complete: () => {
        this.setData({ binding: false })
      }
    })
  },

  selectType(event) {
    this.setData({ currentType: event.currentTarget.dataset.key })
    this.refreshOptions()
  },

  selectIntent(event) {
    this.setData({ captureIntent: event.currentTarget.dataset.key })
    this.refreshOptions()
  },

  onContentInput(event) {
    const content = event.detail.value
    const url = detectUrl(content)
    const updates = { content }
    if (url && !this.data.mediaUrl) {
      updates.mediaUrl = url
      updates.currentType = isVideoLink(url) ? "video_link" : "link"
    }
    this.setData(updates)
    if (updates.currentType) this.refreshOptions()
  },

  onMediaUrlInput(event) {
    const mediaUrl = event.detail.value
    const updates = { mediaUrl }
    if (mediaUrl) updates.currentType = isVideoLink(mediaUrl) ? "video_link" : "link"
    this.setData(updates)
    if (updates.currentType) this.refreshOptions()
  },

  toggleTag(event) {
    const tag = event.currentTarget.dataset.tag
    const selected = this.data.selectedTags.includes(tag)
      ? this.data.selectedTags.filter((item) => item !== tag)
      : [...this.data.selectedTags, tag]
    this.setData({ selectedTags: selected })
    this.refreshOptions()
  },

  onCustomTagInput(event) {
    this.setData({ customTag: event.detail.value })
  },

  addCustomTag() {
    const tag = this.data.customTag.trim()
    if (!tag) return
    if (this.allTags().includes(tag)) {
      this.setData({ customTag: "" })
      return
    }
    this.setData({ customTags: [...this.data.customTags, tag], customTag: "" })
  },

  removeCustomTag(event) {
    const tag = event.currentTarget.dataset.tag
    this.setData({ customTags: this.data.customTags.filter((item) => item !== tag) })
  },

  allTags() {
    return [...this.data.selectedTags, ...this.data.customTags]
  },

  buildDraft(status) {
    const createdAt = nowIso()
    return {
      localId: this.data.editingDraftId || localId(),
      type: this.data.currentType,
      content: this.data.content.trim(),
      mediaUrl: this.data.mediaUrl.trim(),
      tags: this.allTags(),
      captureIntent: this.data.captureIntent,
      status,
      createdAt,
      updatedAt: createdAt,
      remoteSyncStatus: "",
      cloudId: "",
      lastError: ""
    }
  },

  validateDraft(draft) {
    if (!draft.content && !draft.mediaUrl) {
      wx.showToast({ title: "先写内容或粘贴链接", icon: "none" })
      return false
    }
    return true
  },

  upsertDraft(draft) {
    const queue = this.readQueue()
    const index = queue.findIndex((item) => item.localId === draft.localId)
    if (index >= 0) queue[index] = { ...queue[index], ...draft, updatedAt: nowIso() }
    else queue.unshift(draft)
    this.writeQueue(queue.slice(0, 60))
  },

  clearComposer() {
    this.setData({
      currentType: "text",
      captureIntent: "collect",
      content: "",
      mediaUrl: "",
      customTag: "",
      selectedTags: [],
      customTags: [],
      editingDraftId: "",
      submitButtonText: "保存并同步"
    })
    this.refreshOptions()
  },

  saveDraftOnly() {
    const draft = this.buildDraft("draft")
    if (!this.validateDraft(draft)) return
    this.upsertDraft(draft)
    this.clearComposer()
    wx.showToast({ title: "已存草稿", icon: "success" })
  },

  submitInspiration() {
    const draft = this.buildDraft("queued")
    if (!this.validateDraft(draft)) return
    this.upsertDraft(draft)
    this.clearComposer()
    this.syncQueue()
  },

  payloadFor(draft) {
    return {
      id: draft.cloudId || draft.localId,
      type: draft.type,
      content: draft.content,
      media_url: draft.mediaUrl,
      source_url: draft.mediaUrl,
      tags: draft.tags,
      capture_intent: draft.captureIntent,
      target_device_id: this.data.linkedDeviceId,
      client_created_at: draft.createdAt,
      created_at: draft.createdAt
    }
  },

  syncQueue(options = {}) {
    const base = trimUrl(this.data.cloudBaseUrl)
    const queue = this.readQueue()
    const syncable = queue.filter((item) => item.status === "queued")
    if (!syncable.length) {
      this.refreshRecent()
      return
    }
    if (!base) {
      this.markSyncableFailed("未配置同步地址")
      if (!options.quiet) wx.showToast({ title: "先到设置里填同步地址", icon: "none" })
      return
    }
    this.setData({ submitting: true, syncingQueue: true })
    this.syncNext(syncable[0], base, options)
  },

  syncNext(draft, base, options = {}) {
    this.updateDraft(draft.localId, { status: "syncing", lastError: "" })
    wx.request({
      url: `${base}/api/mobile/inspirations`,
      method: "POST",
      data: this.payloadFor(draft),
      success: (response) => {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          const message = response.data && response.data.error ? response.data.error : "云端拒绝提交"
          this.updateDraft(draft.localId, {
            status: "failed",
            lastError: message
          })
          return
        }
        const item = response.data && response.data.item ? response.data.item : {}
        this.updateDraft(draft.localId, {
          status: "synced",
          cloudId: item.id || draft.cloudId || draft.localId,
          remoteSyncStatus: item.sync_status || "pending",
          syncedAt: nowIso(),
          lastError: ""
        })
      },
      fail: () => {
        this.updateDraft(draft.localId, {
          status: "failed",
          lastError: "网络或云端地址不可用"
        })
      },
      complete: () => {
        const pending = this.readQueue().filter((item) => item.status === "queued" && item.localId !== draft.localId)
        if (pending.length) {
          this.syncNext(pending[0], base, options)
          return
        }
        this.setData({ submitting: false, syncingQueue: false })
        this.loadStatus({ quiet: true })
        if (!options.quiet) wx.showToast({ title: "同步处理完成", icon: "success" })
      }
    })
  },

  updateDraft(localId, patch) {
    const queue = this.readQueue().map((item) => (
      item.localId === localId ? { ...item, ...patch, updatedAt: nowIso() } : item
    ))
    this.writeQueue(queue)
  },

  markSyncableFailed(message) {
    const queue = this.readQueue().map((item) => (
      ["queued", "syncing"].includes(item.status) ? { ...item, status: "failed", lastError: message } : item
    ))
    this.writeQueue(queue)
  },

  retryPending() {
    const queue = this.readQueue().map((item) => (
      ["failed"].includes(item.status) ? { ...item, status: "queued", lastError: "" } : item
    ))
    this.writeQueue(queue)
    this.syncQueue()
  },

  retryOne(event) {
    const id = event.currentTarget.dataset.id
    this.updateDraft(id, { status: "queued", lastError: "" })
    this.syncQueue()
  },

  editDraft(event) {
    const id = event.currentTarget.dataset.id
    const draft = this.readQueue().find((item) => item.localId === id)
    if (!draft) return
    const preset = draft.tags.filter((tag) => PRESET_TAGS.includes(tag))
    const custom = draft.tags.filter((tag) => !PRESET_TAGS.includes(tag))
    this.setData({
      editingDraftId: draft.localId,
      currentType: draft.type || "text",
      captureIntent: draft.captureIntent || "collect",
      content: draft.content || "",
      mediaUrl: draft.mediaUrl || "",
      selectedTags: preset,
      customTags: custom,
      customTag: "",
      submitButtonText: "更新并同步"
    })
    this.refreshOptions()
    wx.pageScrollTo({ scrollTop: 0, duration: 200 })
  },

  deleteLocalItem(event) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: "移除本地记录",
      content: "只会移除手机本地记录，不会删除已经同步到云端的内容。",
      confirmColor: "#c7512f",
      success: (result) => {
        if (!result.confirm) return
        const queue = this.readQueue().filter((item) => item.localId !== id)
        this.writeQueue(queue)
      }
    })
  },

  loadStatus(options = {}) {
    const base = trimUrl(this.data.cloudBaseUrl)
    if (!base) return
    this.setData({ loadingStatus: true })
    wx.request({
      url: `${base}/api/mobile/inspirations/status`,
      method: "GET",
      success: (response) => {
        const items = response.data && Array.isArray(response.data.items) ? response.data.items : []
        this.mergeRemoteStatus(items)
        this.setData({ remoteItems: items.slice(-20).reverse() })
      },
      fail: () => {
        if (!options.quiet) wx.showToast({ title: "状态读取失败", icon: "none" })
      },
      complete: () => {
        this.setData({ loadingStatus: false })
        this.refreshRecent()
      }
    })
  },

  mergeRemoteStatus(remoteItems) {
    const byId = {}
    remoteItems.forEach((item) => {
      if (item.id) byId[item.id] = item
    })
    const queue = this.readQueue().map((draft) => {
      const remote = byId[draft.cloudId] || byId[draft.localId]
      if (!remote) return draft
      return {
        ...draft,
        cloudId: remote.id,
        remoteSyncStatus: remote.sync_status || draft.remoteSyncStatus,
        syncedAt: draft.syncedAt || remote.created_at
      }
    })
    this.writeQueue(queue)
  },

  refreshRecent() {
    const localQueue = this.readQueue()
    const localIds = new Set(localQueue.map((item) => item.cloudId || item.localId))
    const remoteOnly = this.data.remoteItems
      .filter((item) => !localIds.has(item.id))
      .map((item) => ({
        localId: item.id,
        cloudId: item.id,
        type: item.type,
        content: item.content,
        mediaUrl: item.media_url,
        tags: item.tags || [],
        captureIntent: item.capture_intent || "collect",
        status: "synced",
        remoteSyncStatus: item.sync_status,
        createdAt: item.created_at
      }))
    const combined = [...localQueue, ...remoteOnly]
      .sort((a, b) => new Date(b.updatedAt || b.createdAt || 0) - new Date(a.updatedAt || a.createdAt || 0))
      .slice(0, 20)
      .map((item) => this.viewModel(item))
    const retryCount = localQueue.filter((item) => ["failed", "queued"].includes(item.status)).length
    const draftCount = localQueue.filter((item) => item.status === "draft").length
    const syncedCount = localQueue.filter((item) => ["synced"].includes(item.status) || item.remoteSyncStatus).length
    let summaryText = "准备收录灵感"
    let summaryTone = "idle"
    if (retryCount) {
      summaryText = `${retryCount} 条待同步，失败也不会丢`
      summaryTone = "warn"
    } else if (draftCount) {
      summaryText = `${draftCount} 条本机草稿`
      summaryTone = "idle"
    } else if (syncedCount) {
      summaryText = `最近已同步 ${syncedCount} 条`
      summaryTone = "ok"
    }
    this.setData({ recentItems: combined, retryCount, summaryText, summaryTone })
  },

  viewModel(item) {
    const type = TYPE_DEFS.find((entry) => entry.key === item.type) || TYPE_DEFS[0]
    const intent = INTENT_DEFS.find((entry) => entry.key === item.captureIntent) || INTENT_DEFS[0]
    const preview = item.content || item.mediaUrl || "未命名灵感"
    const canEdit = ["draft", "failed", "queued"].includes(item.status)
    const canRetry = ["failed"].includes(item.status)
    return {
      localId: item.localId || item.cloudId,
      typeLabel: type.label,
      intentLabel: intent.label,
      preview: preview.length > 80 ? `${preview.slice(0, 80)}...` : preview,
      tagsText: item.tags && item.tags.length ? item.tags.map((tag) => `#${tag}`).join(" ") : "",
      statusText: statusText(item.status, item.remoteSyncStatus),
      statusTone: statusTone(item.status, item.remoteSyncStatus),
      createdLabel: timeLabel(item.createdAt || item.updatedAt),
      canEdit,
      canRetry,
      canDelete: true
    }
  }
})
