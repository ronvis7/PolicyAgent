'use client'

import {Loader2} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet} from '@/components/ui/field'
import {Input} from '@/components/ui/input'
import {Switch} from '@/components/ui/switch'
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
            应用机器人支持卡片内原地忽略并更新为灰色；配置完整时优先使用，发送失败自动回退下方原 Webhook。
            原自定义机器人配置会继续保留，不会重复发送。
            <br/>
            推送状态：
            <span className={config.configured ? 'text-green-600' : 'text-amber-600'}>
              {config.configured ? ` 已开启（${config.webhook_url_masked || '已配置'}）` : ' 未开启'}
            </span>
            {config.configured ? (config.secret_configured ? '，已启用签名校验' : '，未启用签名校验') : ''}
          </FieldDescription>
          <FieldGroup>
            <Field orientation="horizontal">
              <div>
                <FieldLabel htmlFor="feishu_app_enabled">启用应用机器人交互卡片</FieldLabel>
                <FieldDescription className="text-xs">
                  需要飞书权限 im:message:send_as_bot、im:message:update，并配置卡片回传交互。
                </FieldDescription>
              </div>
              <Switch
                id="feishu_app_enabled"
                checked={config.app_enabled ?? false}
                onCheckedChange={(checked) => onChange({...config, app_enabled: checked})}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="feishu_app_id">应用 App ID</FieldLabel>
              <Input id="feishu_app_id" autoComplete="off"
                placeholder={config.app_id_masked || 'cli_…；留空保留现有值'}
                value={config.app_id ?? ''}
                onChange={(e) => onChange({...config, app_id: e.target.value})}/>
            </Field>
            <Field>
              <FieldLabel htmlFor="feishu_app_secret">应用 App Secret</FieldLabel>
              <Input id="feishu_app_secret" type="password" autoComplete="new-password"
                placeholder={config.app_secret_configured ? '已配置；留空保留' : '填写 App Secret'}
                value={config.app_secret ?? ''}
                onChange={(e) => onChange({...config, app_secret: e.target.value})}/>
            </Field>
            <Field>
              <FieldLabel htmlFor="feishu_verification_token">Verification Token</FieldLabel>
              <Input id="feishu_verification_token" type="password" autoComplete="new-password"
                placeholder={config.verification_token_configured ? '已配置；留空保留' : '事件与回调 → 加密策略'}
                value={config.verification_token ?? ''}
                onChange={(e) => onChange({...config, verification_token: e.target.value})}/>
            </Field>
            <Field>
              <FieldLabel htmlFor="feishu_chat_id">目标群 Chat ID</FieldLabel>
              <Input id="feishu_chat_id" autoComplete="off"
                placeholder={config.chat_id_masked || 'oc_…；机器人进群事件也可自动绑定'}
                value={config.chat_id ?? ''}
                onChange={(e) => onChange({...config, chat_id: e.target.value})}/>
              <FieldDescription className="text-xs">
                回调地址：/api/integrations/feishu/card-actions；事件地址：/api/integrations/feishu/events。
                暂时不要开启 Encrypt Key。
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="feishu_webhook_url">原自定义机器人 Webhook（回退）</FieldLabel>
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
