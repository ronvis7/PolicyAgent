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

export default function LoginPage() {
  const {login} = useAuth()
  const router = useRouter()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting) return

    setSubmitting(true)
    try {
      await login({email: email.trim(), password})
      toast.success('登录成功')
      router.replace('/')
    } catch (error) {
      const message = error instanceof ApiError ? error.msg : '登录失败，请稍后重试'
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-screen w-full items-center justify-center bg-[#f8f8f7] px-4">
      <div className="w-full max-w-sm rounded-[18px] border border-[#e5e2de] bg-white p-8 shadow-[0_10px_30px_rgba(16,24,40,.06)]">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 inline-flex rounded-full border border-[#e5e2de] bg-[#f8f8f7] px-3 py-1 text-xs font-semibold text-[#667085]">
            PolicyManus
          </div>
          <h1 className="text-xl font-semibold text-[#202939]">登录 PolicyManus</h1>
          <p className="mt-1 text-sm text-[#778090]">企业政策咨询智能体</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
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
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
            />
          </div>

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting && <Loader2 className="size-4 animate-spin"/>}
            登录
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-[#778090]">
          还没有账号？{' '}
          <Link href="/register" className="font-medium text-[#287174] underline-offset-4 hover:underline">
            注册新组织
          </Link>
        </p>
      </div>
    </div>
  )
}
