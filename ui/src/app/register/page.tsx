'use client'

import React, {useEffect, useState} from 'react'
import Link from 'next/link'
import {useRouter} from 'next/navigation'
import {toast} from 'sonner'
import {Loader2, Search} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Input} from '@/components/ui/input'
import {Label} from '@/components/ui/label'
import {ApiError, authApi} from '@/lib/api'
import type {OrgOption, RegisterMode} from '@/lib/api'
import {useAuth} from '@/providers/auth-provider'

/** 密码最小长度，与后端 RegisterRequest 校验保持一致 */
const MIN_PASSWORD_LENGTH = 8

export default function RegisterPage() {
  const {register} = useAuth()
  const router = useRouter()

  const [mode, setMode] = useState<RegisterMode>('create')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [orgName, setOrgName] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // 加入模式：组织检索与选择
  const [orgQuery, setOrgQuery] = useState('')
  const [orgOptions, setOrgOptions] = useState<OrgOption[]>([])
  const [searchingOrgs, setSearchingOrgs] = useState(false)
  const [selectedOrg, setSelectedOrg] = useState<OrgOption | null>(null)

  // 加入模式下，对检索关键词做防抖检索
  useEffect(() => {
    if (mode !== 'join') return
    let cancelled = false
    setSearchingOrgs(true)
    const timer = setTimeout(() => {
      authApi
        .listOrgs(orgQuery)
        .then((data) => {
          if (!cancelled) setOrgOptions(data?.orgs ?? [])
        })
        .catch(() => {
          if (!cancelled) setOrgOptions([])
        })
        .finally(() => {
          if (!cancelled) setSearchingOrgs(false)
        })
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [mode, orgQuery])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting) return

    if (password.length < MIN_PASSWORD_LENGTH) {
      toast.error(`密码至少需要 ${MIN_PASSWORD_LENGTH} 位`)
      return
    }
    if (password !== confirmPassword) {
      toast.error('两次输入的密码不一致')
      return
    }
    if (mode === 'create' && !orgName.trim()) {
      toast.error('请填写组织名称')
      return
    }
    if (mode === 'join' && !selectedOrg) {
      toast.error('请选择要加入的组织')
      return
    }

    setSubmitting(true)
    try {
      await register({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        mode,
        org_name: mode === 'create' ? orgName.trim() : '',
        org_id: mode === 'join' ? selectedOrg!.id : '',
      })
      toast.success(
        mode === 'join'
          ? '注册成功，加入申请已提交，待管理员批准前你在临时个人工作区'
          : '注册成功',
      )
      router.replace('/')
    } catch (error) {
      const message = error instanceof ApiError ? error.msg : '注册失败，请稍后重试'
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-gradient-to-b from-muted via-background to-accent px-4 py-8">
      <div className="w-full max-w-sm rounded-[20px] border border-border bg-card p-8 shadow-[var(--shadow-pop)]">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1 text-xs font-semibold text-foreground">
            <span className="size-2 rounded-full bg-primary"/>
            PolicyManus
          </div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight text-foreground">注册 PolicyManus</h1>
          <p className="mt-1 text-sm text-muted-foreground">创建新组织，或申请加入已有组织</p>
        </div>

        {/* 模式切换 */}
        <div className="mb-2 grid grid-cols-2 gap-2 rounded-lg bg-muted p-1">
          {(['create', 'join'] as RegisterMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded-md py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                mode === m ? 'bg-card shadow-sm text-foreground' : 'text-muted-foreground'
              }`}
            >
              {m === 'create' ? '创建新组织' : '加入已有组织'}
            </button>
          ))}
        </div>

        {/* 场景化说明：帮助用户区分"自己建"还是"加入同事的" */}
        <div className="mb-5 rounded-lg border border-border bg-background px-3 py-2 text-xs leading-5 text-muted-foreground">
          {mode === 'create' ? (
            <>
              <span className="font-medium text-foreground">适合：你为自己的公司/单位首次建立工作区。</span>
              <br />
              你将成为所有者，立即拥有完整工作区并开始填写企业档案。
            </>
          ) : (
            <>
              <span className="font-medium text-foreground">适合：你的同事已建好公司工作区，你想加入它。</span>
              <br />
              提交后需等待该组织管理员<span className="font-medium text-[#b54708]">批准</span>；批准前你会先进入一个临时的个人工作区。
            </>
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 创建模式：组织名 */}
          {mode === 'create' && (
            <div className="space-y-2">
              <Label htmlFor="org_name">组织名称</Label>
              <Input
                id="org_name"
                required
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="例如：重庆理工大学"
              />
              <p className="text-xs text-muted-foreground">名称需唯一，你将成为该组织的所有者。</p>
            </div>
          )}

          {/* 加入模式：检索并选择组织 */}
          {mode === 'join' && (
            <div className="space-y-2">
              <Label htmlFor="org_query">选择要加入的组织</Label>
              <div className="relative">
                <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground"/>
                <Input
                  id="org_query"
                  className="pl-8"
                  value={orgQuery}
                  onChange={(e) => {
                    setOrgQuery(e.target.value)
                    setSelectedOrg(null)
                  }}
                  placeholder="输入组织名搜索"
                />
              </div>
              {selectedOrg ? (
                <div className="flex items-center justify-between rounded-md border bg-muted/40 px-3 py-2 text-sm">
                  <span>已选择：<span className="font-medium">{selectedOrg.name}</span></span>
                  <button
                    type="button"
                    className="text-xs text-muted-foreground underline cursor-pointer"
                    onClick={() => setSelectedOrg(null)}
                  >
                    重选
                  </button>
                </div>
              ) : (
                <div className="max-h-40 overflow-y-auto rounded-md border">
                  {searchingOrgs && (
                    <div className="flex justify-center py-3">
                      <Loader2 className="size-4 animate-spin text-muted-foreground"/>
                    </div>
                  )}
                  {!searchingOrgs && orgOptions.length === 0 && (
                    <div className="py-3 text-center text-xs text-muted-foreground">
                      未找到组织
                    </div>
                  )}
                  {!searchingOrgs && orgOptions.map((org) => (
                    <button
                      key={org.id}
                      type="button"
                      onClick={() => setSelectedOrg(org)}
                      className="block w-full px-3 py-2 text-left text-sm hover:bg-muted cursor-pointer"
                    >
                      {org.name}
                    </button>
                  ))}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                提交后将向该组织管理员发起加入申请，批准前你可在个人工作区使用自己的 API Key。
              </p>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="display_name">你的姓名</Label>
            <Input
              id="display_name"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="例如：张三"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">邮箱</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={MIN_PASSWORD_LENGTH}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={`至少 ${MIN_PASSWORD_LENGTH} 位`}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm_password">确认密码</Label>
            <Input
              id="confirm_password"
              type="password"
              autoComplete="new-password"
              required
              minLength={MIN_PASSWORD_LENGTH}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="再次输入密码"
            />
          </div>

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting && <Loader2 className="size-4 animate-spin"/>}
            {mode === 'join' ? '注册并申请加入' : '注册并创建组织'}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          已有账号？{' '}
          <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            去登录
          </Link>
        </p>
      </div>
    </div>
  )
}
