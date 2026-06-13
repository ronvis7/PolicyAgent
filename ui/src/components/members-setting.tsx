'use client'

import {useCallback, useEffect, useRef, useState} from 'react'
import {toast} from 'sonner'
import {Loader2, Trash, UserPlus} from 'lucide-react'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {Button} from '@/components/ui/button'
import {Input} from '@/components/ui/input'
import {Switch} from '@/components/ui/switch'
import {Badge} from '@/components/ui/badge'
import {Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet} from '@/components/ui/field'
import {Item, ItemContent, ItemDescription, ItemGroup, ItemTitle} from '@/components/ui/item'
import {membershipApi} from '@/lib/api'
import type {MemberItem, MembershipRole} from '@/lib/api'
import {useAuth} from '@/providers/auth-provider'

const ROLE_LABEL: Record<MembershipRole, string> = {
  owner: '所有者',
  admin: '管理员',
  member: '成员',
}

/**
 * 组织成员管理。
 *
 * 列表对 owner/admin 可见(由父级设置弹窗把控进入)；所有者不可被改角色或移除，
 * 当前登录用户自身不可对自己操作。增删改后端同样会再次校验。
 */
export function MembersSetting() {
  const {user} = useAuth()
  const [members, setMembers] = useState<MemberItem[]>([])
  const [requests, setRequests] = useState<MemberItem[]>([])
  const [loading, setLoading] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [addEmail, setAddEmail] = useState('')
  const [addAsAdmin, setAddAsAdmin] = useState(false)
  const [adding, setAdding] = useState(false)
  // 正在进行行内操作的 membership_id，用于禁用按钮防重复
  const [busyId, setBusyId] = useState<string | null>(null)
  const fetchingRef = useRef(false)

  const fetchMembers = useCallback(() => {
    if (fetchingRef.current) return
    fetchingRef.current = true
    setLoading(true)
    Promise.all([membershipApi.list(), membershipApi.listRequests()])
      .then(([memberData, requestData]) => {
        setMembers(memberData?.members ?? [])
        setRequests(requestData?.members ?? [])
      })
      .catch((err) => {
        console.error('[Members] 获取成员/申请列表失败:', err)
        toast.error(err instanceof Error ? err.message : '获取成员列表失败')
      })
      .finally(() => {
        setLoading(false)
        fetchingRef.current = false
      })
  }, [])

  useEffect(() => {
    fetchMembers()
  }, [fetchMembers])

  const handleAdd = async () => {
    const email = addEmail.trim().toLowerCase()
    if (!email) {
      toast.error('请输入待添加成员的邮箱')
      return
    }
    setAdding(true)
    try {
      await membershipApi.add({email, role: addAsAdmin ? 'admin' : 'member'})
      toast.success('添加成员成功')
      setAddEmail('')
      setAddAsAdmin(false)
      setAddOpen(false)
      fetchMembers()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '添加成员失败')
    } finally {
      setAdding(false)
    }
  }

  const handleApprove = async (member: MemberItem) => {
    setBusyId(member.membership_id)
    try {
      await membershipApi.approve(member.membership_id)
      toast.success(`已批准 ${member.email} 加入`)
      fetchMembers()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '批准失败')
    } finally {
      setBusyId(null)
    }
  }

  const handleReject = async (member: MemberItem) => {
    setBusyId(member.membership_id)
    try {
      await membershipApi.reject(member.membership_id)
      toast.success(`已拒绝 ${member.email} 的申请`)
      setRequests((prev) => prev.filter((m) => m.membership_id !== member.membership_id))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '拒绝失败')
    } finally {
      setBusyId(null)
    }
  }

  const handleToggleRole = async (member: MemberItem) => {
    const nextRole: MembershipRole = member.role === 'admin' ? 'member' : 'admin'
    setBusyId(member.membership_id)
    try {
      await membershipApi.changeRole(member.membership_id, nextRole)
      toast.success(`已将 ${member.email} 设为${ROLE_LABEL[nextRole]}`)
      fetchMembers()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '变更角色失败')
    } finally {
      setBusyId(null)
    }
  }

  const handleRemove = async (member: MemberItem) => {
    setBusyId(member.membership_id)
    try {
      await membershipApi.remove(member.membership_id)
      toast.success(`已移除 ${member.email}`)
      setMembers((prev) => prev.filter((m) => m.membership_id !== member.membership_id))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '移除成员失败')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="w-full px-1">
      <FieldGroup>
        <FieldSet>
          <FieldLegend className="w-full flex justify-between items-center text-lg font-bold text-gray-700">
            组织成员
            <Dialog open={addOpen} onOpenChange={setAddOpen}>
              <DialogTrigger asChild>
                <Button type="button" size="xs" className="cursor-pointer">
                  <UserPlus className="size-4"/>
                  添加成员
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle className="text-gray-700">添加成员</DialogTitle>
                </DialogHeader>
                <form
                  className="w-full"
                  onSubmit={(e) => {
                    e.preventDefault()
                    handleAdd()
                  }}
                >
                  <FieldGroup>
                    <FieldSet>
                      <Field>
                        <FieldLabel htmlFor="member_email">成员邮箱</FieldLabel>
                        <Input
                          id="member_email"
                          type="email"
                          placeholder="对方需已注册账号"
                          value={addEmail}
                          onChange={(e) => setAddEmail(e.target.value)}
                          disabled={adding}
                        />
                        <FieldDescription className="text-xs">
                          仅能添加已注册的用户；对方注册后即可被加入本组织。
                        </FieldDescription>
                      </Field>
                      <div className="flex items-center gap-2">
                        <Switch
                          id="member_as_admin"
                          checked={addAsAdmin}
                          onCheckedChange={setAddAsAdmin}
                          disabled={adding}
                        />
                        <FieldLabel htmlFor="member_as_admin" className="!mb-0">设为管理员</FieldLabel>
                      </div>
                    </FieldSet>
                  </FieldGroup>
                </form>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline" className="cursor-pointer" disabled={adding}>取消</Button>
                  </DialogClose>
                  <Button className="cursor-pointer" onClick={handleAdd} disabled={adding}>
                    {adding && <Loader2 className="animate-spin"/>}
                    添加
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </FieldLegend>
          <FieldDescription className="text-sm">
            管理本组织成员：添加已注册用户、将成员设为管理员或移除。所有者不可被变更或移除。
          </FieldDescription>

          {/* 待审批的加入申请 */}
          {!loading && requests.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50/60 p-3">
              <div className="mb-2 text-sm font-semibold text-amber-700">
                待审批的加入申请（{requests.length}）
              </div>
              <ItemGroup className="gap-2">
                {requests.map((req) => {
                  const busy = busyId === req.membership_id
                  return (
                    <Item key={req.membership_id} variant="outline" className="bg-white">
                      <ItemContent>
                        <ItemTitle className="w-full flex justify-between items-center text-sm font-medium text-gray-700">
                          <div className="flex flex-col">
                            <span>{req.display_name || req.email}</span>
                            <span className="text-xs text-muted-foreground">{req.email}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              type="button"
                              size="xs"
                              className="cursor-pointer"
                              disabled={busy}
                              onClick={() => handleApprove(req)}
                            >
                              {busy && <Loader2 className="animate-spin"/>}
                              批准
                            </Button>
                            <Button
                              type="button"
                              size="xs"
                              variant="outline"
                              className="cursor-pointer"
                              disabled={busy}
                              onClick={() => handleReject(req)}
                            >
                              拒绝
                            </Button>
                          </div>
                        </ItemTitle>
                      </ItemContent>
                    </Item>
                  )
                })}
              </ItemGroup>
            </div>
          )}

          {loading && (
            <div className="flex justify-center py-8">
              <Loader2 className="size-6 animate-spin text-muted-foreground"/>
            </div>
          )}

          {!loading && members.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              暂无成员
            </div>
          )}

          {!loading && members.length > 0 && (
            <ItemGroup className="gap-3">
              {members.map((member) => {
                const isOwner = member.role === 'owner'
                const isSelf = member.email === user?.email
                const locked = isOwner || isSelf
                const busy = busyId === member.membership_id
                return (
                  <Item key={member.membership_id} variant="outline">
                    <ItemContent>
                      <ItemTitle className="w-full flex justify-between items-center text-md font-bold text-gray-700">
                        <div className="flex gap-2 items-center">
                          {member.display_name || member.email}
                          <Badge variant={isOwner ? 'default' : 'secondary'}>
                            {ROLE_LABEL[member.role]}
                          </Badge>
                          {isSelf && <Badge variant="outline" className="text-gray-400">我</Badge>}
                        </div>
                        <div className="flex items-center justify-center gap-2">
                          {!locked && (
                            <Button
                              type="button"
                              variant="outline"
                              size="xs"
                              className="cursor-pointer"
                              disabled={busy}
                              onClick={() => handleToggleRole(member)}
                            >
                              {busy && <Loader2 className="animate-spin"/>}
                              {member.role === 'admin' ? '设为成员' : '设为管理员'}
                            </Button>
                          )}
                          {!locked && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-xs"
                              className="cursor-pointer"
                              disabled={busy}
                              onClick={() => handleRemove(member)}
                            >
                              <Trash/>
                            </Button>
                          )}
                        </div>
                      </ItemTitle>
                      <ItemDescription>{member.email}</ItemDescription>
                    </ItemContent>
                  </Item>
                )
              })}
            </ItemGroup>
          )}
        </FieldSet>
      </FieldGroup>
    </div>
  )
}
