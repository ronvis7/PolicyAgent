/** 工作台未读数变化的浏览器事件名。
 *
 * 无 WebSocket，前端用一个轻量自定义事件在 Feed 页与左栏之间同步未读红点：
 * Feed 页清未读/重算后 dispatch，左栏监听后重新拉取 unread-count。
 */
export const FEED_UNREAD_CHANGED_EVENT = 'feed:unread-changed'
