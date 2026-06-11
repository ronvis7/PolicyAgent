'use client'

import React, {useState} from 'react'
import Link from 'next/link'
import {useRouter} from 'next/navigation'
import {toast} from 'sonner'
import {Loader2} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {Input} from '@/components/ui/input'
import {Label} from '@/components/ui/label'
import {ApiError} from '@/lib/api'
import {useAuth} from '@/providers/auth-provider'

/** 密码最小长度，与后端 RegisterRequest 校验保持一致 */
const MIN_PASSWORD_LENGTH = 8

export default function RegisterPage() {
  const {register} = useAuth()
  const router = useRouter()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [orgName, setOrgName] = useState('')
  const [submitting, setSubmitting] = useState(false)

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

    setSubmitting(true)
    try {
      await register({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        org_name: orgName.trim(),
      })
      toast.success('注册成功')
      router.replace('/')
    } catch (error) {
      const message = error instanceof ApiError ? error.msg : '注册失败，请稍后重试'
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-screen w-full items-center justify-center bg-[#f8f8f7] px-4">
      <div className="w-full max-w-sm rounded-xl border bg-white p-8 shadow-sm">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold">注册 PolicyManus</h1>
          <p className="mt-1 text-sm text-muted-foreground">创建你的组织，开始使用</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="org_name">组织名称</Label>
            <Input
              id="org_name"
              required
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="例如：示范企业"
            />
          </div>

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
            注册并创建组织
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          已有账号？{' '}
          <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
            去登录
          </Link>
        </p>
      </div>
    </div>
  )
}
