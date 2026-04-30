import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AutoComplete,
  Button,
  DatePicker,
  Drawer,
  Form,
  Input,
  Layout,
  Popover,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  SearchOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  MobileOutlined,
  TabletOutlined,
  ControlOutlined,
  CheckOutlined,
} from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import { apiRequest } from '../shared/api';
import { getUserDisplayName } from '../shared/auth';
import PersonDisplay, { personFromBorrower } from '../shared/PersonDisplay';
import { BorrowRequestItem, Device, LLMModel, LLMModelAssignments, PortalUser } from '../shared/types';
import {
  extractPerformance,
  formatDateTime,
  pickPerformanceColor,
  pickTagColor,
  toDayjs,
  toISOString,
} from '../shared/utils';

type SortOrder = 'ascend' | 'descend';

function normalizeSorter(
  sorter: unknown
): { columnKey?: string; order?: SortOrder } {
  if (Array.isArray(sorter)) {
    return sorter[0] || {};
  }
  if (sorter && typeof sorter === 'object') {
    return sorter as { columnKey?: string; order?: SortOrder };
  }
  return {};
}

function BorrowDrawer(props: {
  open: boolean;
  device: Device | null;
  currentUser: PortalUser;
  onCancel: () => void;
  onConfirm: (expected: Dayjs) => void;
}) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (!props.open) return;
    form.resetFields();
  }, [props.open, form]);

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={420} title={`借用设备 ${props.device?.model || ''}`}>
      <Form layout="vertical" form={form}>
        <Form.Item label="借用人">
          <div className="drawer-person-panel">
            <PersonDisplay person={props.currentUser} size="medium" showJobTitle />
          </div>
        </Form.Item>
        <Form.Item
          label="预计归还时间"
          name="expected"
          rules={[{ required: true, message: '请选择预计归还时间' }]}
        >
          <DatePicker
            showTime
            style={{ width: '100%' }}
            disabledDate={(current) => current && current < dayjs().startOf('day')}
          />
        </Form.Item>
      </Form>
      <div className="drawer-footer">
        <Button onClick={props.onCancel}>取消</Button>
        <Button
          type="primary"
          onClick={() => {
            form
              .validateFields()
              .then((values) => props.onConfirm(values.expected))
              .catch(() => message.error('请填写借用信息'));
          }}
        >
          确认借用
        </Button>
      </div>
    </Drawer>
  );
}

function ChangeBorrowerDrawer(props: {
  open: boolean;
  device: Device | null;
  currentUser: PortalUser;
  onCancel: () => void;
  onConfirm: (expected: Dayjs) => void;
}) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (!props.open) return;
    form.setFieldsValue({
      expected: toDayjs(props.device?.expected_return_at) || undefined,
    });
  }, [props.open, props.device, form]);

  return (
    <Drawer
      open={props.open}
      onClose={props.onCancel}
      width={420}
      title={`变更借用人 ${props.device?.model || ''}`}
    >
      <Form layout="vertical" form={form}>
        <Form.Item label="原借用人">
          <div className="drawer-person-panel">
            <PersonDisplay person={personFromBorrower(props.device || {})} size="medium" showJobTitle />
          </div>
        </Form.Item>
        <Form.Item label="新借用人名字">
          <div className="drawer-person-panel">
            <PersonDisplay person={props.currentUser} size="medium" showJobTitle />
          </div>
        </Form.Item>
        <Form.Item
          label="预计归还时间"
          name="expected"
          rules={[{ required: true, message: '请选择预计归还时间' }]}
        >
          <DatePicker
            showTime
            style={{ width: '100%' }}
            disabledDate={(current) => current && current < dayjs().startOf('day')}
          />
        </Form.Item>
      </Form>
      <div className="drawer-footer">
        <Button onClick={props.onCancel}>取消</Button>
        <Button
          type="primary"
          onClick={() => {
            form
              .validateFields()
              .then((values) => props.onConfirm(values.expected))
              .catch(() => message.error('请填写借用信息'));
          }}
        >
          确认
        </Button>
      </div>
    </Drawer>
  );
}

function ExtendDrawer(props: {
  open: boolean;
  device: Device | null;
  onCancel: () => void;
  onConfirm: (expected: Dayjs) => void;
}) {
  const [form] = Form.useForm();
  const minDate = useMemo(() => toDayjs(props.device?.expected_return_at), [props.device]);

  useEffect(() => {
    if (!props.open) return;
    form.resetFields();
  }, [props.open, form]);

  const disabledDate = (current: Dayjs) => {
    if (!minDate) return false;
    return current && current < minDate.startOf('day');
  };

  const disabledTime = (current: Dayjs | null) => {
    if (!minDate || !current) return {};
    if (!current.isSame(minDate, 'day')) return {};
    const minHour = minDate.hour();
    const minMinute = minDate.minute();
    const minSecond = minDate.second();
    return {
      disabledHours: () => Array.from({ length: minHour }, (_, i) => i),
      disabledMinutes: (hour: number) =>
        hour === minHour ? Array.from({ length: minMinute }, (_, i) => i) : [],
      disabledSeconds: (hour: number, minute: number) =>
        hour === minHour && minute === minMinute
          ? Array.from({ length: minSecond + 1 }, (_, i) => i)
          : [],
    };
  };

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={420} title={`延期 ${props.device?.model || ''}`}>
      <Form layout="vertical" form={form}>
        <Form.Item
          label="新的预计归还时间"
          name="expected"
          rules={[{ required: true, message: '请选择新的归还时间' }]}
        >
          <DatePicker
            showTime
            style={{ width: '100%' }}
            disabledDate={disabledDate}
            disabledTime={disabledTime}
          />
        </Form.Item>
      </Form>
      <div className="drawer-footer">
        <Button onClick={props.onCancel}>取消</Button>
        <Button
          type="primary"
          onClick={() => {
            form
              .validateFields()
              .then((values) => props.onConfirm(values.expected))
              .catch(() => message.error('请选择延期时间'));
          }}
        >
          确认延期
        </Button>
      </div>
    </Drawer>
  );
}

export default function BorrowApp(props: { currentUser: PortalUser }) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [aiReason, setAiReason] = useState('');
  const [borrowDevice, setBorrowDevice] = useState<Device | null>(null);
  const [changeBorrowDevice, setChangeBorrowDevice] = useState<Device | null>(null);
  const [extendDevice, setExtendDevice] = useState<Device | null>(null);
  const [detailDevice, setDetailDevice] = useState<Device | null>(null);
  const [sortState, setSortState] = useState<{ key: string; order: SortOrder } | null>({
    key: 'status',
    order: 'ascend',
  });
  const [modelName, setModelName] = useState('未配置');
  const [modelLoading, setModelLoading] = useState(false);
  const [deviceTotal, setDeviceTotal] = useState(0);
  const [fastModelId, setFastModelId] = useState<number | null>(null);
  const [accurateModelId, setAccurateModelId] = useState<number | null>(null);
  const [fastModelName, setFastModelName] = useState('未配置');
  const [accurateModelName, setAccurateModelName] = useState('未配置');
  const [assignmentsReady, setAssignmentsReady] = useState(false);
  const [devicePage, setDevicePage] = useState(1);
  const [blockedBorrowTipDeviceId, setBlockedBorrowTipDeviceId] = useState<number | null>(null);
  const blockedBorrowTipTimerRef = useRef<number | null>(null);
  const [aiMode, setAiMode] = useState<'fast' | 'accurate' | null>(() => {
    const stored = localStorage.getItem('ai_search_mode');
    if (stored === 'fast' || stored === 'accurate') {
      return stored;
    }
    return null;
  });
  const loanStatusOrder: Record<string, number> = {
    available: 0,
    pending: 1,
    borrowed: 2,
  };
  const performanceOrder: Record<string, number> = {
    强劲: 0,
    较高: 1,
    一般: 2,
    较低: 3,
  };
  const unregisteredBorrowTipText =
    '未找到该设备的借用人，无法进行设备借用，请找回设备后，把状态改回“正常”。';
  const getStatusRank = (value?: string | null) => (value === '正常' ? 0 : 1);
  const compareStatus = (a?: string | null, b?: string | null) => {
    const diff = getStatusRank(a) - getStatusRank(b);
    if (diff !== 0) return diff;
    return (a || '').localeCompare(b || '');
  };
  const getPerformanceRank = (notes?: string | null) => {
    const value = extractPerformance(notes);
    return performanceOrder[value] ?? 99;
  };
  const filterBorrowVisibleDevices = (items: Device[]) =>
    items.filter((item) => item.status !== '损坏');

  const loadDevices = async (q?: string) => {
    setLoading(true);
    try {
      const url = q ? `/api/devices?query=${encodeURIComponent(q)}` : '/api/devices';
      const data = await apiRequest<{ items: Device[] }>(url);
      const visibleItems = filterBorrowVisibleDevices(data.items || []);
      setDevices(visibleItems);
      setAiReason('');
      if (!q) {
        setDeviceTotal(visibleItems.length);
      }
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChangeBorrower = async (record: Device) => {
    try {
      const res = await apiRequest<{ items: BorrowRequestItem[] }>(
        `/api/borrow-requests?status=pending&device_id=${record.id}&request_type=change`
      );
      if ((res.items || []).length > 0) {
        message.warning('当前设备已有借用人更换申请，需等待管理员处理。');
        return;
      }
      setChangeBorrowDevice(record);
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const refreshDeviceStatus = async () => {
    try {
      const data = await apiRequest<{ items: Device[] }>('/api/devices');
      const visibleItems = filterBorrowVisibleDevices(data.items || []);
      const latest = new Map(visibleItems.map((item) => [item.id, item]));
      setDeviceTotal(visibleItems.length);
      setDevices((prev) =>
        prev
          .filter((item) => latest.has(item.id))
          .map((item) => {
            const fresh = latest.get(item.id);
            if (!fresh) return item;
            return fresh;
          })
      );
    } catch {
      // background refresh should stay silent
    }
  };

  const applyAssignments = (items: LLMModel[], assignments: LLMModelAssignments) => {
    const fastId = assignments.fast_model_id ?? null;
    const accurateId = assignments.accurate_model_id ?? null;
    const fastModel = items.find((item) => item.id === fastId);
    const accurateModel = items.find((item) => item.id === accurateId);
    setFastModelId(fastModel ? fastId : null);
    setAccurateModelId(accurateModel ? accurateId : null);
    setFastModelName(fastModel ? fastModel.name || fastModel.model || '未配置' : '未配置');
    setAccurateModelName(accurateModel ? accurateModel.name || accurateModel.model || '未配置' : '未配置');
  };

  const loadModelState = async () => {
    setModelLoading(true);
    try {
      const [modelRes, assignmentRes] = await Promise.all([
        apiRequest<{ items: LLMModel[] }>('/api/llm/models'),
        apiRequest<LLMModelAssignments>('/api/llm/models/assignments'),
      ]);
      const items = modelRes.items || [];
      const current = items.find((item) => Boolean(item.is_default)) || items[0];
      if (current) {
        setModelName(current.name || current.model || '未配置');
      } else {
        setModelName('未配置');
      }
      applyAssignments(items, assignmentRes);
    } catch (err) {
      setModelName('未配置');
      setFastModelId(null);
      setAccurateModelId(null);
      setFastModelName('未配置');
      setAccurateModelName('未配置');
    } finally {
      setModelLoading(false);
      setAssignmentsReady(true);
    }
  };

  useEffect(() => {
    loadDevices();
    loadModelState();
  }, []);

  useEffect(() => {
    return () => {
      if (blockedBorrowTipTimerRef.current) {
        window.clearTimeout(blockedBorrowTipTimerRef.current);
      }
    };
  }, []);

  const showBlockedBorrowTip = (deviceId: number) => {
    setBlockedBorrowTipDeviceId(deviceId);
    if (blockedBorrowTipTimerRef.current) {
      window.clearTimeout(blockedBorrowTipTimerRef.current);
    }
    blockedBorrowTipTimerRef.current = window.setTimeout(() => {
      setBlockedBorrowTipDeviceId((current) => (current === deviceId ? null : current));
      blockedBorrowTipTimerRef.current = null;
    }, 5000);
  };

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      refreshDeviceStatus();
    }, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const columns = [
    {
      title: '设备型号',
      dataIndex: 'model',
      key: 'model',
      sorter: (a: Device, b: Device) => (a.model || '').localeCompare(b.model || ''),
      sortOrder: sortState?.key === 'model' ? sortState.order : null,
    },
    {
      title: '设备状态',
      dataIndex: 'status',
      key: 'status',
      sorter: (a: Device, b: Device) => compareStatus(a.status, b.status),
      sortOrder: sortState?.key === 'status' ? sortState.order : null,
      render: (value: string) => <Tag color={value === '正常' ? 'green' : 'volcano'}>{value}</Tag>,
    },
    {
      title: '设备类型',
      dataIndex: 'type',
      key: 'type',
      sorter: (a: Device, b: Device) => (a.type || '').localeCompare(b.type || ''),
      sortOrder: sortState?.key === 'type' ? sortState.order : null,
      render: (value: string | null) => {
        if (value === '手机') {
          return (
            <Space size={6} className="device-type device-type-phone">
              <MobileOutlined />
              <span>手机</span>
            </Space>
          );
        }
        if (value === '平板') {
          return (
            <Space size={6} className="device-type device-type-tablet">
              <TabletOutlined />
              <span>平板</span>
            </Space>
          );
        }
        if (value === '手柄') {
          return (
            <Space size={6} className="device-type device-type-controller">
              <ControlOutlined />
              <span>手柄</span>
            </Space>
          );
        }
        return '-';
      },
    },
    {
      title: '厂商',
      dataIndex: 'vendor_name',
      key: 'vendor_name',
      sorter: (a: Device, b: Device) => (a.vendor_name || '').localeCompare(b.vendor_name || ''),
      sortOrder: sortState?.key === 'vendor_name' ? sortState.order : null,
      render: (value: string) =>
        value ? (
          <Tag color={pickTagColor(value)} className="tag-emphasis">
            {value}
          </Tag>
        ) : (
          '-'
        ),
    },
    {
      title: '系统',
      dataIndex: 'system_name',
      key: 'system_name',
      sorter: (a: Device, b: Device) => (a.system_name || '').localeCompare(b.system_name || ''),
      sortOrder: sortState?.key === 'system_name' ? sortState.order : null,
      render: (value: string) =>
        value ? (
          <Tag color={pickTagColor(value)} className="tag-emphasis">
            {value}
          </Tag>
        ) : (
          '-'
        ),
    },
    {
      title: '系统版本',
      dataIndex: 'system_version',
      key: 'system_version',
      sorter: (a: Device, b: Device) => (a.system_version || '').localeCompare(b.system_version || ''),
      sortOrder: sortState?.key === 'system_version' ? sortState.order : null,
      render: (value: string) =>
        value ? (
          <Tag color={pickTagColor(value)} className="tag-emphasis">
            {value}
          </Tag>
        ) : (
          '-'
        ),
    },
    {
      title: '性能',
      key: 'performance',
      width: 84,
      sorter: (a: Device, b: Device) => {
        const diff = getPerformanceRank(a.notes) - getPerformanceRank(b.notes);
        if (diff !== 0) return diff;
        return (a.id ?? 0) - (b.id ?? 0);
      },
      sortOrder: sortState?.key === 'performance' ? sortState.order : null,
      render: (_: unknown, record: Device) => {
        const value = extractPerformance(record.notes);
        return value === '-' ? '-' : <Tag color={pickPerformanceColor(value)}>{value}</Tag>;
      },
    },
    {
      title: '详情',
      key: 'details',
      render: (_: unknown, record: Device) => (
        <Button size="small" onClick={() => setDetailDevice(record)}>
          详情
        </Button>
      ),
    },
    {
      title: '借用人',
      dataIndex: 'borrower_name',
      key: 'borrower_name',
      align: 'center' as const,
      render: (_: string, record: Device) => {
        const borrower = record.borrower_name?.trim();
        const currentUserName = getUserDisplayName(props.currentUser).trim();
        const canChangeBorrower = Boolean(borrower && borrower !== currentUserName);
        return (
          <Space direction="vertical" size={4} align="center">
            <PersonDisplay person={personFromBorrower(record)} size="small" />
            {canChangeBorrower ? (
              <Button size="small" onClick={() => handleOpenChangeBorrower(record)}>
                换借用人
              </Button>
            ) : null}
          </Space>
        );
      },
    },
    {
      title: '借用时间',
      dataIndex: 'borrowed_at',
      key: 'borrowed_at',
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '预计归还时间',
      dataIndex: 'expected_return_at',
      key: 'expected_return_at',
      render: (_: string, record: Device) => (
        <Space direction="vertical" size={4}>
          <span>{formatDateTime(record.expected_return_at)}</span>
          {record.loan_status === 'borrowed' ? (
            <Button size="small" onClick={() => setExtendDevice(record)}>
              延期
            </Button>
          ) : null}
        </Space>
      ),
    },
    {
      title: '借用操作',
      key: 'loan_status',
      sorter: (a: Device, b: Device) =>
        (loanStatusOrder[a.loan_status] ?? 99) - (loanStatusOrder[b.loan_status] ?? 99),
      sortOrder: sortState?.key === 'loan_status' ? sortState.order : null,
      render: (_: unknown, record: Device) => {
        const isAvailable = record.loan_status === 'available';
        const isPending = record.loan_status === 'pending';
        const isBorrowed = record.loan_status === 'borrowed';
        const isUnregisteredBorrow = record.status === '未登记借用';
        const canBorrow = isAvailable && !isUnregisteredBorrow;
        const showUnregisteredBorrowTip = isAvailable && isUnregisteredBorrow;
        const borrowButton = (
          <button
            type="button"
            className={`loan-status-segment ${isAvailable ? 'is-active is-available' : ''} ${
              canBorrow ? 'is-clickable' : ''
            } ${showUnregisteredBorrowTip ? 'is-blocked' : ''}`}
            disabled={!isAvailable && !showUnregisteredBorrowTip}
            onClick={() => {
              if (canBorrow) {
                setBorrowDevice(record);
                return;
              }
              if (showUnregisteredBorrowTip) {
                showBlockedBorrowTip(record.id);
              }
            }}
          >
            可借
          </button>
        );
        return (
          <div className="loan-status-group" role="group" aria-label="借用状态">
            {showUnregisteredBorrowTip ? (
              <Popover
                trigger="click"
                content={unregisteredBorrowTipText}
                open={blockedBorrowTipDeviceId === record.id}
                onOpenChange={(open) => {
                  if (!open && blockedBorrowTipDeviceId === record.id) {
                    setBlockedBorrowTipDeviceId(null);
                  }
                }}
              >
                {borrowButton}
              </Popover>
            ) : (
              borrowButton
            )}
            <span
              className={`loan-status-segment ${isPending ? 'is-active is-pending' : ''}`}
              aria-disabled="true"
            >
              待借
            </span>
            <span
              className={`loan-status-segment ${isBorrowed ? 'is-active is-borrowed' : ''}`}
              aria-disabled="true"
            >
              已借
            </span>
          </div>
        );
      },
    },
  ];

  const sortedDevices = useMemo(() => {
    if (!sortState) return devices;
    const sorted = [...devices];
    const { key, order } = sortState;
    const isDesc = order === 'descend';
    if (key === 'performance') {
      sorted.sort((a, b) => {
        const diff = getPerformanceRank(a.notes) - getPerformanceRank(b.notes);
        if (diff !== 0) {
          return isDesc ? -diff : diff;
        }
        return (a.id ?? 0) - (b.id ?? 0);
      });
      return sorted;
    }
    if (key === 'status') {
      sorted.sort((a, b) => {
        const diff = compareStatus(a.status, b.status);
        return isDesc ? -diff : diff;
      });
      return sorted;
    }
    const getValue = (item: Device) => {
      switch (key) {
        case 'model':
          return item.model || '';
        case 'type':
          return item.type || '';
        case 'vendor_name':
          return item.vendor_name || '';
        case 'system_name':
          return item.system_name || '';
        case 'system_version':
          return item.system_version || '';
        case 'loan_status':
          return String(loanStatusOrder[item.loan_status] ?? 99);
        default:
          return '';
      }
    };
    sorted.sort((a, b) => getValue(a).localeCompare(getValue(b)));
    if (isDesc) {
      sorted.reverse();
    }
    return sorted;
  }, [devices, sortState]);
  const searchOptions = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const values = new Set<string>();
    devices.forEach((device) => {
      if (device.model) values.add(device.model);
      if (device.vendor_name) values.add(device.vendor_name);
      if (device.system_name) values.add(device.system_name);
      if (device.system_version) values.add(device.system_version);
    });
    return Array.from(values)
      .filter((item) => !keyword || item.toLowerCase().includes(keyword))
      .slice(0, 20)
      .map((value) => ({ value }));
  }, [devices, query]);
  const canSelectFast = Boolean(fastModelId);
  const canSelectAccurate = Boolean(accurateModelId);
  const selectedModelName =
    aiMode === 'fast' && canSelectFast
      ? fastModelName
      : aiMode === 'accurate' && canSelectAccurate
        ? accurateModelName
        : modelName;
  const smartSearchLabel = modelLoading ? '智能搜索(加载中)' : `智能搜索(${selectedModelName})`;

  useEffect(() => {
    if (!assignmentsReady) return;
    if (!aiMode && canSelectFast) {
      setAiMode('fast');
      localStorage.setItem('ai_search_mode', 'fast');
      return;
    }
    if (aiMode === 'fast' && !canSelectFast) {
      setAiMode(null);
      localStorage.removeItem('ai_search_mode');
    }
    if (aiMode === 'accurate' && !canSelectAccurate) {
      setAiMode(null);
      localStorage.removeItem('ai_search_mode');
    }
  }, [aiMode, assignmentsReady, canSelectFast, canSelectAccurate]);

  return (
    <Layout className="app-layout">
      <Layout.Header className="app-header">
        <div className="app-header-content">
          <Space direction="vertical" size={2}>
            <Typography.Title level={4} style={{ margin: 0 }}>
              设备借用助手 · 借用页
            </Typography.Title>
            <Typography.Text type="secondary">快速查找与借用设备，支持智能搜索与延期。</Typography.Text>
          </Space>
          <PersonDisplay person={props.currentUser} size="medium" showJobTitle className="header-user" />
        </div>
      </Layout.Header>
      <Layout.Content className="app-content">
        <div className="page">
          <section className="table-card">
            <div className="table-header">
              <div className="table-actions">
                <AutoComplete
                  value={query}
                  options={searchOptions}
                  onSearch={(value) => setQuery(value)}
                  onSelect={(value) => setQuery(value)}
                  onChange={(value) => setQuery(value)}
                  style={{ width: 280 }}
                  allowClear
                >
                  <Input placeholder="输入型号/系统/厂商等关键词" />
                </AutoComplete>
                <Button
                  icon={<SearchOutlined />}
                  onClick={() => {
                    setDevicePage(1);
                    loadDevices(query.trim());
                  }}
                  disabled={aiLoading}
                >
                  普通搜索
                </Button>
                <Button.Group className="ai-mode-group">
                  <Button
                    icon={<ThunderboltOutlined />}
                    onClick={async () => {
                      const value = query.trim();
                      if (!value) {
                        message.error('请输入搜索内容');
                        return;
                      }
                      setAiLoading(true);
                      try {
                        const data = await apiRequest<{ items: Device[]; ai_reason?: string }>('/api/llm/search', {
                          method: 'POST',
                          body: { query: value, mode: aiMode || undefined },
                        });
                        const visibleItems = filterBorrowVisibleDevices(data.items || []);
                        setDevices(visibleItems);
                        setAiReason(data.ai_reason || '');
                        setDevicePage(1);
                        if (!visibleItems.length) {
                          message.error('未找到匹配设备');
                        }
                      } catch (err) {
                        setAiReason('');
                        message.error((err as Error).message || 'AI 模型服务暂不可用');
                      } finally {
                        setAiLoading(false);
                      }
                    }}
                    loading={aiLoading}
                    className="ai-mode-main"
                  >
                    {smartSearchLabel}
                  </Button>
                  <Button
                    type={aiMode === 'fast' ? 'primary' : 'default'}
                    onClick={() => {
                      setAiMode('fast');
                      localStorage.setItem('ai_search_mode', 'fast');
                    }}
                    disabled={!canSelectFast}
                    className="ai-mode-toggle"
                    icon={aiMode === 'fast' ? <CheckOutlined /> : undefined}
                  >
                    更快
                  </Button>
                  <Button
                    type={aiMode === 'accurate' ? 'primary' : 'default'}
                    onClick={() => {
                      setAiMode('accurate');
                      localStorage.setItem('ai_search_mode', 'accurate');
                    }}
                    disabled={!canSelectAccurate}
                    className="ai-mode-toggle"
                    icon={aiMode === 'accurate' ? <CheckOutlined /> : undefined}
                  >
                    更准
                  </Button>
                </Button.Group>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => {
                    setQuery('');
                    setAiReason('');
                    setDevicePage(1);
                    loadDevices();
                  }}
                  disabled={aiLoading}
                >
                  清除
                </Button>
              </div>
              <Space>
                <Typography.Text className="muted">设备总数：{deviceTotal}</Typography.Text>
                {aiLoading ? (
                  <Space className="muted">
                    <Spin size="small" />
                    <Typography.Text className="muted">AI 正在查找匹配设备...</Typography.Text>
                  </Space>
                ) : null}
                {loading ? <Spin size="small" /> : null}
              </Space>
            </div>
            <div className="ai-reason">
              <Typography.Text strong>智能搜索输出</Typography.Text>
              <Input.TextArea
                value={aiReason}
                placeholder="暂无智能搜索输出"
                readOnly
                autoSize={{ minRows: 2, maxRows: 4 }}
              />
            </div>
            <Table
              rowKey="id"
              dataSource={sortedDevices}
              columns={columns}
              pagination={{ pageSize: 20, current: devicePage }}
              tableLayout="fixed"
              size="small"
              className="full-table"
              sortDirections={['ascend', 'descend']}
              sticky={{ offsetHeader: 120 }}
              onChange={(pagination, __, sorter, extra) => {
                if (extra?.action === 'paginate') {
                  setDevicePage(pagination.current || 1);
                  return;
                }
                if (extra?.action === 'sort') {
                  const { columnKey, order } = normalizeSorter(sorter);
                  if (!columnKey) return;
                  const nextOrder: SortOrder =
                    order || (sortState?.key === columnKey && sortState.order === 'ascend' ? 'descend' : 'ascend');
                  setSortState({ key: columnKey, order: nextOrder });
                  setDevicePage(1);
                }
              }}
            />
          </section>

          <BorrowDrawer
            open={Boolean(borrowDevice)}
            device={borrowDevice}
            currentUser={props.currentUser}
            onCancel={() => setBorrowDevice(null)}
            onConfirm={async (expected) => {
              if (!borrowDevice) return;
              const iso = toISOString(expected);
              if (!iso) {
                message.error('请选择预计归还时间');
                return;
              }
              try {
                await apiRequest(`/api/devices/${borrowDevice.id}/borrow`, {
                  method: 'POST',
                  body: { borrower_name: getUserDisplayName(props.currentUser), expected_return_at: iso },
                });
                message.success({ content: '已通知管理员，请前往管理员出借用设备', duration: 8 });
                setBorrowDevice(null);
                loadDevices();
              } catch (err) {
                message.error((err as Error).message);
              }
            }}
          />

          <ChangeBorrowerDrawer
            open={Boolean(changeBorrowDevice)}
            device={changeBorrowDevice}
            currentUser={props.currentUser}
            onCancel={() => setChangeBorrowDevice(null)}
            onConfirm={async (expected) => {
              if (!changeBorrowDevice) return;
              const iso = toISOString(expected);
              if (!iso) {
                message.error('请选择预计归还时间');
                return;
              }
              try {
                await apiRequest(`/api/devices/${changeBorrowDevice.id}/change-borrower`, {
                  method: 'POST',
                  body: { borrower_name: getUserDisplayName(props.currentUser), expected_return_at: iso },
                });
                message.success({ content: '已发送通知到管理员，请等待管理员确认操作。', duration: 5 });
                setChangeBorrowDevice(null);
                loadDevices(query.trim() || undefined);
              } catch (err) {
                message.error((err as Error).message);
              }
            }}
          />

          <ExtendDrawer
            open={Boolean(extendDevice)}
            device={extendDevice}
            onCancel={() => setExtendDevice(null)}
            onConfirm={async (expected) => {
              if (!extendDevice) return;
              const iso = toISOString(expected);
              if (!iso) {
                message.error('请选择延期时间');
                return;
              }
              try {
                await apiRequest(`/api/devices/${extendDevice.id}/extend`, {
                  method: 'POST',
                  body: { expected_return_at: iso },
                });
                message.success('延期成功');
                setExtendDevice(null);
                loadDevices();
              } catch (err) {
                message.error((err as Error).message);
              }
            }}
          />
          <Drawer
            open={Boolean(detailDevice)}
            onClose={() => setDetailDevice(null)}
            width={420}
            title={`设备详情 ${detailDevice ? `#${detailDevice.id}` : ''}`}
          >
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Typography.Text strong>设备ID</Typography.Text>
              <Typography.Text>{detailDevice?.id ?? '-'}</Typography.Text>
              <Typography.Text strong>分辨率</Typography.Text>
              <Typography.Text>{detailDevice?.resolution || '-'}</Typography.Text>
              <Typography.Text strong>架构</Typography.Text>
              <Typography.Text>{detailDevice?.arch || '-'}</Typography.Text>
              <Typography.Text strong>CPU型号</Typography.Text>
              <Typography.Text>{detailDevice?.cpu || '-'}</Typography.Text>
              <Typography.Text strong>开机密码</Typography.Text>
              <Typography.Text>{detailDevice?.boot_password || '-'}</Typography.Text>
              <Typography.Text strong>备注</Typography.Text>
              <Typography.Text>{detailDevice?.notes || '-'}</Typography.Text>
            </Space>
          </Drawer>
        </div>
      </Layout.Content>
    </Layout>
  );
}
