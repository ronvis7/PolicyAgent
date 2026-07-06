'use client'

import {Loader2} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet} from '@/components/ui/field'
import {Input} from '@/components/ui/input'
import type {FeishuConfig} from '@/lib/api'

type FeishuSettingProps = {
  config: FeishuConfig
  onChange: (config: FeishuConfig) => void
  onTest: () => void
  onClear: () => void
  testing: boolean
  clearing: boolean
}

/**
 * 飞书推送设置表单（设置弹窗「飞书推送」页签）。
 * 保存动作由弹窗底部统一的「保存」按钮触发；本组件只负责表单与测试/停用操作。
 */
export function FeishuSetting({config, onChange, onTest, onClear, testing, clearing}: FeishuSettingProps) {
  return (
    <form className="w-full px-1" onSubmit={(e) => e.preventDefault()}>
      <FieldGroup>
        <FieldSet>
          <FieldLegend className="text-lg font-bold text-gray-700">飞书推送（新赛事即推）</FieldLegend>
          <FieldDescription className="text-sm">
            新赛事机会入库后即时推送到本组织的飞书群，并按企业档案的「参赛关注地区」过滤。
            配置方法：建群 → 群设置添加「自定义机器人」→ 复制 webhook 地址填入（建议同时开启「签名校验」并填入密钥）。
            <br/>
            推送状态：
            <span className={config.configured ? 'text-green-600' : 'text-amber-600'}>
              {config.configured ? ` 已开启（${config.webhook_url_masked || '已配置'}）` : ' 未开启'}
            </span>
            {config.configured ? (config.secret_configured ? '，已启用签名校验' : '，未启用签名校验') : ''}
          </FieldDescription>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="feishu_webhook_url">机器人 webhook 地址</FieldLabel>
              <Input
                id="feishu_webhook_url"
                type="text"
                autoComplete="off"
                placeholder={config.configured
                  ? '留空保留当前已配置的地址'
                  : 'https://open.feishu.cn/open-apis/bot/v2/hook/…'}
                value={config.webhook_url ?? ''}
                onChange={(e) => onChange({...config, webhook_url: e.target.value})}
              />
              <FieldDescription className="text-xs">
                webhook 地址即推送凭据，仅保存到服务端、页面只回显脱敏尾号。仅支持飞书官方地址（https://open.feishu.cn/ 开头）。
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="feishu_secret">签名校验密钥（可选）</FieldLabel>
              <Input
                id="feishu_secret"
                type="password"
                autoComplete="new-password"
                placeholder="机器人开启签名校验后的密钥；地址不变时留空则保留当前密钥"
                value={config.secret ?? ''}
                onChange={(e) => onChange({...config, secret: e.target.value})}
              />
              <FieldDescription className="text-xs">
                与机器人「签名校验」开关保持一致：机器人开了校验必须填，未开则留空。
                换新 webhook 地址时旧密钥不会沿用，请一并填写新密钥（新机器人未开校验则留空）。
              </FieldDescription>
            </Field>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                className="cursor-pointer"
                disabled={!config.configured || testing}
                onClick={onTest}
              >
                {testing && <Loader2 className="animate-spin"/>}
                发送测试消息
              </Button>
              <Button
                type="button"
                variant="outline"
                className="cursor-pointer text-destructive"
                disabled={!config.configured || clearing}
                onClick={onClear}
              >
                {clearing && <Loader2 className="animate-spin"/>}
                停用推送
              </Button>
            </div>
            <FieldDescription className="text-xs">
              「发送测试消息」用已保存的配置向群里发一条验证消息；修改后请先保存再测试。
              「停用推送」会清除已保存的地址与密钥，重新开启需再次到飞书群复制 webhook。
            </FieldDescription>
          </FieldGroup>
        </FieldSet>
      </FieldGroup>
    </form>
  )
}
