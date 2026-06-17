'use client'

/**
 * 助手品牌字标。
 *
 * 原为 Manus 原型字样 SVG，现统一为 PolicyManus 文字字标，
 * 颜色随父级 `currentColor`（普通消息灰、错误消息红）。
 */
export function ManusIcon() {
  return (
    <span className="text-xs font-semibold tracking-wide" style={{color: 'var(--logo-color, currentColor)'}}>
      PolicyManus
    </span>
  )
}
