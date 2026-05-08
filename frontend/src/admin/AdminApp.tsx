import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  App,
  AutoComplete,
  Button,
  Card,
  Drawer,
  Form,
  Input,
  Layout,
  Menu,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
  Spin,
  Switch,
  Badge,
  Collapse,
} from 'antd';
import {
  PlusOutlined,
  SettingOutlined,
  EditOutlined,
  DeleteOutlined,
  RollbackOutlined,
  DatabaseOutlined,
  MobileOutlined,
  TabletOutlined,
  ControlOutlined,
  SearchOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  CheckOutlined,
  AppstoreOutlined,
  ClockCircleOutlined,
  ProfileOutlined,
  ExportOutlined,
  BellOutlined,
} from '@ant-design/icons';
import { apiRequest } from '../shared/api';
import PersonDisplay, { personFromBorrower, personFromChange } from '../shared/PersonDisplay';
import {
  BorrowRecord,
  BorrowRequestItem,
  Device,
  LLMModel,
  LLMModelAssignments,
  NotificationParams,
  NotificationSettingItem,
  NotificationSettingsResponse,
  WebhookNotificationParams,
  WebhookNotificationSettingItem,
  WebhookNotificationSettingsResponse,
  SystemItem,
  SystemVersion,
  PortalUser,
  Vendor,
} from '../shared/types';
import { extractPerformance, formatDateTime, pickPerformanceColor, pickTagColor } from '../shared/utils';

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

const STATUS_OPTIONS = ['正常', '未登记借用', '损坏', '被常驻', '报修'];
const TYPE_OPTIONS = ['手机', '平板', '手柄'];
const NOTIFICATION_PARAM_FIELDS: Array<keyof NotificationParams> = [
  'card_title',
  'status',
  'card_color',
  'status_color',
];
const WEBHOOK_NOTIFICATION_PARAM_FIELDS: Array<keyof WebhookNotificationParams> = [
  'card_title',
  'body_template',
  'card_color',
];
const DEFAULT_BORROW_ADMIN_URL = 'http://192.168.50.10:8090/admin';
const getStatusRank = (value?: string | null) => (value === '正常' ? 0 : 1);
const compareStatus = (a?: string | null, b?: string | null) => {
  const diff = getStatusRank(a) - getStatusRank(b);
  if (diff !== 0) return diff;
  return (a || '').localeCompare(b || '');
};

function renderDeviceType(value: string | null): ReactNode {
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
}

interface DrawerState {
  type:
    | 'device-form'
    | 'vendor-list'
    | 'vendor-form'
    | 'vendor-delete'
    | 'vendor-rebind'
    | 'system-list'
    | 'system-form'
    | 'version-form'
    | 'system-delete'
    | 'version-delete'
    | 'system-rebind'
    | 'version-rebind'
    | 'device-delete'
    | 'device-return'
    | 'notify'
    | 'model-list'
    | 'model-form'
    | 'model-delete';
  payload?: unknown;
}

interface VersionPayload {
  system: SystemItem;
  version: SystemVersion;
}

function ConfirmDrawer(props: {
  open: boolean;
  title: string;
  description: string;
  confirmText: string;
  confirmType?: 'primary' | 'default' | 'dashed' | 'link' | 'text';
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}) {
  return (
    <Drawer
      open={props.open}
      onClose={props.onCancel}
      width={420}
      title={props.title}
    >
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Typography.Paragraph style={{ marginBottom: 0 }}>
          {props.description}
        </Typography.Paragraph>
        {props.children}
        <div className="drawer-footer">
          <Button onClick={props.onCancel}>取消</Button>
          <Button
            type={props.confirmType || 'primary'}
            danger={props.danger}
            onClick={props.onConfirm}
          >
            {props.confirmText}
          </Button>
        </div>
      </Space>
    </Drawer>
  );
}

function DeviceFormDrawer(props: {
  open: boolean;
  device?: Device | null;
  draft?: Record<string, unknown> | null;
  vendors: Vendor[];
  systems: SystemItem[];
  onCancel: () => void;
  onSaved: (values: Record<string, unknown>, device?: Device | null) => void;
  onDelete: (device: Device) => void;
  onAddVendor: (draft: Record<string, unknown>, device?: Device | null) => void;
  onAddSystem: (draft: Record<string, unknown>, device?: Device | null) => void;
  onAddVersion: (draft: Record<string, unknown>, system: SystemItem, device?: Device | null) => void;
}) {
  const [form] = Form.useForm();
  const [versions, setVersions] = useState<SystemVersion[]>([]);

  useEffect(() => {
    if (!props.open) return;
    const source = (props.draft ?? props.device) as Partial<Device> | null;
    if (!source) {
      form.resetFields();
      setVersions([]);
      return;
    }
    form.setFieldsValue({
      model: source.model || undefined,
      status: source.status || undefined,
      type: source.type || undefined,
      vendor_id: source.vendor_id ?? undefined,
      system_id: source.system_id ?? undefined,
      system_version_id: source.system_version_id ?? undefined,
      resolution: source.resolution || undefined,
      arch: source.arch || undefined,
      cpu: source.cpu || undefined,
      boot_password: source.boot_password || undefined,
      notes: source.notes || undefined,
    });
    const systemId = source.system_id ? Number(source.system_id) : null;
    const system = systemId ? props.systems.find((item) => item.id === systemId) : undefined;
    setVersions(system?.versions || []);
  }, [props.open, props.device, props.draft, props.systems, form]);

  const handleSystemChange = (value: number) => {
    const system = props.systems.find((item) => item.id === value);
    setVersions(system?.versions || []);
    form.setFieldsValue({ system_version_id: undefined });
  };
  const buildDraft = () => form.getFieldsValue();
  const renderDropdownFooter = (label: string, onClick: () => void) => (
    <div style={{ borderTop: '1px solid #f0f0f0', padding: '8px 12px' }}>
      <Button type="link" icon={<PlusOutlined />} onClick={onClick}>
        {label}
      </Button>
    </div>
  );

  return (
    <Drawer
      open={props.open}
      onClose={props.onCancel}
      width={520}
      title={props.device ? `编辑设备 #${props.device.id}` : '添加设备'}
    >
      <Form layout="vertical" form={form}>
        <Form.Item
          label="设备型号"
          name="model"
          rules={[{ required: true, message: '设备型号不能为空' }]}
        >
          <Input placeholder="输入设备型号" />
        </Form.Item>
        <Form.Item
          label="设备状态"
          name="status"
          rules={[{ required: true, message: '设备状态不能为空' }]}
        >
          <Select placeholder="选择设备状态" options={STATUS_OPTIONS.map((item) => ({ value: item }))} />
        </Form.Item>
        <Form.Item label="设备类型" name="type">
          <Select
            placeholder="选择设备类型"
            allowClear
            options={TYPE_OPTIONS.map((item) => ({ value: item }))}
          />
        </Form.Item>
        <Form.Item
          label="厂商"
          name="vendor_id"
          rules={[{ required: true, message: '厂商不能为空' }]}
        >
          <Select
            placeholder="选择厂商"
            options={props.vendors.map((item) => ({ value: item.id, label: item.name }))}
            dropdownRender={(menu) => (
              <>
                {menu}
                {renderDropdownFooter('新增厂商', () => props.onAddVendor(buildDraft(), props.device))}
              </>
            )}
          />
        </Form.Item>
        <Form.Item
          label="系统"
          name="system_id"
          rules={[{ required: true, message: '系统不能为空' }]}
        >
          <Select
            placeholder="选择系统"
            options={props.systems.map((item) => ({ value: item.id, label: item.name }))}
            onChange={handleSystemChange}
            dropdownRender={(menu) => (
              <>
                {menu}
                {renderDropdownFooter('新增系统', () => props.onAddSystem(buildDraft(), props.device))}
              </>
            )}
          />
        </Form.Item>
        <Form.Item
          label="系统版本"
          name="system_version_id"
          rules={[{ required: true, message: '系统版本不能为空' }]}
        >
          <Select
            placeholder="选择系统版本"
            options={versions.map((item) => ({ value: item.id, label: item.version }))}
            dropdownRender={(menu) => (
              <>
                {menu}
                {renderDropdownFooter('新增版本', () => {
                  const draft = buildDraft();
                  const systemId = draft.system_id ? Number(draft.system_id) : null;
                  const system = systemId ? props.systems.find((item) => item.id === systemId) : null;
                  if (!system) {
                    message.error('请先选择系统');
                    return;
                  }
                  props.onAddVersion(draft, system, props.device);
                })}
              </>
            )}
          />
        </Form.Item>
        <Form.Item label="分辨率" name="resolution">
          <Input placeholder="例如 1080x2400" />
        </Form.Item>
        <Form.Item label="架构" name="arch">
          <Input placeholder="例如 arm64" />
        </Form.Item>
        <Form.Item label="CPU 型号" name="cpu">
          <Input placeholder="例如 Snapdragon" />
        </Form.Item>
        <Form.Item label="开机密码" name="boot_password">
          <Input placeholder="设备开机密码" />
        </Form.Item>
        <Form.Item label="备注" name="notes">
          <Input.TextArea rows={3} placeholder="补充说明" />
        </Form.Item>
      </Form>
      <div className="drawer-footer">
        {props.device && (
          <Button danger onClick={() => props.device && props.onDelete(props.device)}>
            删除设备
          </Button>
        )}
        <Button
          type="primary"
          onClick={() => {
            form
              .validateFields()
              .then((values) => props.onSaved(values, props.device))
              .catch(() => message.error('请填写关键字段'));
          }}
        >
          确认
        </Button>
      </div>
    </Drawer>
  );
}

function VendorListDrawer(props: {
  open: boolean;
  vendors: Vendor[];
  onClose: () => void;
  onAdd: () => void;
  onEdit: (vendor: Vendor) => void;
  onDelete: (vendor: Vendor) => void;
}) {
  return (
    <Drawer open={props.open} onClose={props.onClose} width={520} title="厂商配置">
      <Table
        rowKey="id"
        dataSource={props.vendors}
        pagination={false}
        columns={[
          { title: '厂商', dataIndex: 'name', key: 'name' },
          {
            title: '操作',
            key: 'actions',
            render: (_, record) => (
              <Space>
                <Button size="small" onClick={() => props.onEdit(record)}>
                  编辑
                </Button>
                <Button size="small" danger onClick={() => props.onDelete(record)}>
                  删除
                </Button>
              </Space>
            ),
          },
        ]}
      />
      <div className="drawer-footer">
        <Button type="primary" icon={<PlusOutlined />} onClick={props.onAdd}>
          新增厂商
        </Button>
      </div>
    </Drawer>
  );
}

function VendorFormDrawer(props: {
  open: boolean;
  vendor?: Vendor | null;
  vendors: Vendor[];
  onCancel: () => void;
  onSaved: (name: string, vendor?: Vendor | null) => void;
}) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (!props.open) return;
    form.setFieldsValue({ name: props.vendor?.name || '' });
  }, [props.open, props.vendor, form]);

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={420} title={props.vendor ? '编辑厂商' : '新增厂商'}>
      <Form layout="vertical" form={form}>
        <Form.Item
          label="厂商名称"
          name="name"
          rules={[{ required: true, message: '厂商不能为空' }]}
        >
          <Input placeholder="输入厂商名称" />
        </Form.Item>
      </Form>
      <div className="drawer-footer">
        <Button onClick={props.onCancel}>取消</Button>
        <Button
          type="primary"
          onClick={() => {
            form
              .validateFields()
              .then((values) => {
                const name = String(values.name || '').trim();
                if (!name) {
                  message.error('厂商不能为空');
                  return;
                }
                if (props.vendors.some((item) => item.name === name && item.id !== props.vendor?.id)) {
                  message.error('厂商已存在');
                  return;
                }
                props.onSaved(name, props.vendor);
              })
              .catch(() => null);
          }}
        >
          确认
        </Button>
      </div>
    </Drawer>
  );
}

function VendorRebindDrawer(props: {
  open: boolean;
  vendor: Vendor | null;
  vendors: Vendor[];
  onCancel: () => void;
  onConfirm: (targetId: number) => void;
}) {
  const [target, setTarget] = useState<number | null>(null);

  useEffect(() => {
    if (props.open) {
      setTarget(null);
    }
  }, [props.open]);

  const options = props.vendors.filter((item) => item.id !== props.vendor?.id);

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={420} title="重新绑定厂商">
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Paragraph style={{ marginBottom: 0 }}>
          该厂商已绑定设备，请选择新的厂商进行绑定。
        </Typography.Paragraph>
        <Select
          placeholder="请选择新的厂商"
          value={target ?? undefined}
          onChange={(value) => setTarget(value)}
          options={options.map((item) => ({ value: item.id, label: item.name }))}
        />
        <div className="drawer-footer">
          <Button onClick={props.onCancel}>取消</Button>
          <Button
            type="primary"
            disabled={!target}
            onClick={() => target && props.onConfirm(target)}
          >
            确认
          </Button>
        </div>
      </Space>
    </Drawer>
  );
}

function SystemListDrawer(props: {
  open: boolean;
  systems: SystemItem[];
  onClose: () => void;
  onAddSystem: () => void;
  onEditSystem: (system: SystemItem) => void;
  onDeleteSystem: (system: SystemItem) => void;
  onAddVersion: (system: SystemItem) => void;
  onDeleteVersion: (system: SystemItem, version: SystemVersion) => void;
}) {
  return (
    <Drawer open={props.open} onClose={props.onClose} width={720} title="系统配置">
      <div className="card-stack">
        {props.systems.map((system) => (
          <Card
            key={system.id}
            title={<Typography.Text strong>{system.name}</Typography.Text>}
            extra={
              <Space>
                <Button size="small" onClick={() => props.onAddVersion(system)}>
                  新增版本
                </Button>
                <Button size="small" onClick={() => props.onEditSystem(system)}>
                  编辑
                </Button>
                <Button size="small" danger onClick={() => props.onDeleteSystem(system)}>
                  删除
                </Button>
              </Space>
            }
          >
            <Space wrap>
              {system.versions && system.versions.length ? (
                system.versions.map((version) => (
                  <Tag
                    key={version.id}
                    closable
                    onClose={(e) => {
                      e.preventDefault();
                      props.onDeleteVersion(system, version);
                    }}
                  >
                    {version.version}
                  </Tag>
                ))
              ) : (
                <Typography.Text className="muted">暂无版本</Typography.Text>
              )}
            </Space>
          </Card>
        ))}
        {!props.systems.length && <Typography.Text className="muted">暂无系统配置</Typography.Text>}
      </div>
      <div className="drawer-footer">
        <Button type="primary" icon={<PlusOutlined />} onClick={props.onAddSystem}>
          新增系统
        </Button>
      </div>
    </Drawer>
  );
}

function SystemFormDrawer(props: {
  open: boolean;
  system?: SystemItem | null;
  systems: SystemItem[];
  onCancel: () => void;
  onSaved: (name: string, system?: SystemItem | null) => void;
}) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (!props.open) return;
    form.setFieldsValue({ name: props.system?.name || '' });
  }, [props.open, props.system, form]);

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={420} title={props.system ? '编辑系统' : '新增系统'}>
      <Form layout="vertical" form={form}>
        <Form.Item
          label="系统名称"
          name="name"
          rules={[{ required: true, message: '系统不能为空' }]}
        >
          <Input placeholder="输入系统名称" />
        </Form.Item>
      </Form>
      <div className="drawer-footer">
        <Button onClick={props.onCancel}>取消</Button>
        <Button
          type="primary"
          onClick={() => {
            form
              .validateFields()
              .then((values) => {
                const name = String(values.name || '').trim();
                if (!name) {
                  message.error('系统不能为空');
                  return;
                }
                if (props.systems.some((item) => item.name === name && item.id !== props.system?.id)) {
                  message.error('系统已存在');
                  return;
                }
                props.onSaved(name, props.system);
              })
              .catch(() => null);
          }}
        >
          确认
        </Button>
      </div>
    </Drawer>
  );
}

function VersionFormDrawer(props: {
  open: boolean;
  system: SystemItem | null;
  onCancel: () => void;
  onSaved: (version: string, system: SystemItem) => void;
}) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (props.open) {
      form.resetFields();
    }
  }, [props.open, form]);

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={420} title="新增版本">
      <Form layout="vertical" form={form}>
        <Form.Item label="系统">
          <div className="tag-pill">{props.system?.name || '-'}</div>
        </Form.Item>
        <Form.Item
          label="版本名称"
          name="version"
          rules={[{ required: true, message: '版本不能为空' }]}
        >
          <Input placeholder="输入版本" />
        </Form.Item>
      </Form>
      <div className="drawer-footer">
        <Button onClick={props.onCancel}>取消</Button>
        <Button
          type="primary"
          onClick={() => {
            form
              .validateFields()
              .then((values) => {
                const version = String(values.version || '').trim();
                if (!props.system) return;
                if (
                  props.system.versions &&
                  props.system.versions.some((item) => item.version === version)
                ) {
                  message.error('版本已存在');
                  return;
                }
                props.onSaved(version, props.system);
              })
              .catch(() => null);
          }}
        >
          确认
        </Button>
      </div>
    </Drawer>
  );
}

function SystemRebindDrawer(props: {
  open: boolean;
  system: SystemItem | null;
  systems: SystemItem[];
  onCancel: () => void;
  onConfirm: (systemId: number, versionId: number) => void;
}) {
  const [targetSystem, setTargetSystem] = useState<number | null>(null);
  const [targetVersion, setTargetVersion] = useState<number | null>(null);

  const availableSystems = props.systems.filter((item) => item.id !== props.system?.id);
  const versionOptions = useMemo(() => {
    const target = availableSystems.find((item) => item.id === targetSystem);
    return target?.versions || [];
  }, [availableSystems, targetSystem]);

  useEffect(() => {
    if (props.open) {
      setTargetSystem(null);
      setTargetVersion(null);
    }
  }, [props.open]);

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={420} title="重新绑定系统">
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Paragraph style={{ marginBottom: 0 }}>
          该系统已绑定设备，请选择新的系统与版本进行绑定。
        </Typography.Paragraph>
        <Select
          placeholder="请选择新的系统"
          value={targetSystem ?? undefined}
          onChange={(value) => {
            setTargetSystem(value);
            setTargetVersion(null);
          }}
          options={availableSystems.map((item) => ({ value: item.id, label: item.name }))}
        />
        <Select
          placeholder="请选择新的版本"
          value={targetVersion ?? undefined}
          onChange={(value) => setTargetVersion(value)}
          options={versionOptions.map((item) => ({ value: item.id, label: item.version }))}
          disabled={!targetSystem}
        />
        <div className="drawer-footer">
          <Button onClick={props.onCancel}>取消</Button>
          <Button
            type="primary"
            disabled={!targetSystem || !targetVersion}
            onClick={() =>
              targetSystem && targetVersion && props.onConfirm(targetSystem, targetVersion)
            }
          >
            确认
          </Button>
        </div>
      </Space>
    </Drawer>
  );
}

function VersionRebindDrawer(props: {
  open: boolean;
  system: SystemItem | null;
  version: SystemVersion | null;
  onCancel: () => void;
  onConfirm: (versionId: number) => void;
}) {
  const [target, setTarget] = useState<number | null>(null);
  const versions = props.system?.versions?.filter((item) => item.id !== props.version?.id) || [];

  useEffect(() => {
    if (props.open) {
      setTarget(null);
    }
  }, [props.open]);

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={420} title="重新绑定版本">
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Paragraph style={{ marginBottom: 0 }}>
          该版本已绑定设备，请选择新的版本进行绑定。
        </Typography.Paragraph>
        <Select
          placeholder="请选择新的版本"
          value={target ?? undefined}
          onChange={(value) => setTarget(value)}
          options={versions.map((item) => ({ value: item.id, label: item.version }))}
        />
        <div className="drawer-footer">
          <Button onClick={props.onCancel}>取消</Button>
          <Button type="primary" disabled={!target} onClick={() => target && props.onConfirm(target)}>
            确认
          </Button>
        </div>
      </Space>
    </Drawer>
  );
}

function NotifyDrawer(props: {
  open: boolean;
  onCancel: () => void;
}) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<NotificationSettingItem[]>([]);
  const [webhookSettings, setWebhookSettings] = useState<WebhookNotificationSettingItem[]>([]);
  const [colorOptions, setColorOptions] = useState<string[]>([]);
  const [selectedKey, setSelectedKey] = useState('');
  const [selectedWebhookKey, setSelectedWebhookKey] = useState('');
  const selectedSetting = useMemo(
    () => settings.find((item) => item.key === selectedKey) || settings[0] || null,
    [settings, selectedKey]
  );
  const selectedWebhookSetting = useMemo(
    () => webhookSettings.find((item) => item.key === selectedWebhookKey) || webhookSettings[0] || null,
    [webhookSettings, selectedWebhookKey]
  );
  const previewParams: NotificationParams = {
    card_title: String(Form.useWatch('card_title', form) ?? selectedSetting?.params.card_title ?? ''),
    status: String(Form.useWatch('status', form) ?? selectedSetting?.params.status ?? ''),
    card_color: String(Form.useWatch('card_color', form) ?? selectedSetting?.params.card_color ?? 'blue'),
    status_color: String(Form.useWatch('status_color', form) ?? selectedSetting?.params.status_color ?? 'blue'),
  };
  const webhookPreviewParams: WebhookNotificationParams = {
    card_title: String(
      Form.useWatch('webhook_card_title', form) ?? selectedWebhookSetting?.params.card_title ?? ''
    ),
    body_template: String(
      Form.useWatch('webhook_body_template', form) ?? selectedWebhookSetting?.params.body_template ?? ''
    ),
    card_color: String(Form.useWatch('webhook_card_color', form) ?? selectedWebhookSetting?.params.card_color ?? 'blue'),
  };
  const adminUrlPreview = String(Form.useWatch('admin_url', form) ?? DEFAULT_BORROW_ADMIN_URL);

  useEffect(() => {
    if (!props.open) return;
    setLoading(true);
    Promise.all([
      apiRequest<{ webhook_url: string; admin_url: string }>('/api/settings/feishu'),
      apiRequest<NotificationSettingsResponse>('/api/settings/notifications'),
      apiRequest<WebhookNotificationSettingsResponse>('/api/settings/webhook-notifications'),
    ])
      .then(([feishuData, notificationData, webhookNotificationData]) => {
        const items = notificationData.items || [];
        const webhookItems = webhookNotificationData.items || [];
        setSettings(items);
        setWebhookSettings(webhookItems);
        setColorOptions(notificationData.color_options || []);
        setSelectedKey(items[0]?.key || '');
        setSelectedWebhookKey(webhookItems[0]?.key || '');
        form.setFieldsValue({
          webhook: feishuData.webhook_url || '',
          admin_url: feishuData.admin_url || webhookNotificationData.admin_url || DEFAULT_BORROW_ADMIN_URL,
          ...(items[0]?.params || {}),
          webhook_card_title: webhookItems[0]?.params.card_title || '',
          webhook_body_template: webhookItems[0]?.params.body_template || '',
          webhook_card_color: webhookItems[0]?.params.card_color || 'blue',
        });
      })
      .catch((err) => message.error(err.message))
      .finally(() => setLoading(false));
  }, [props.open, form]);

  useEffect(() => {
    if (!props.open || !selectedSetting) return;
    form.setFieldsValue(selectedSetting.params);
  }, [props.open, selectedKey, form]);

  useEffect(() => {
    if (!props.open || !selectedWebhookSetting) return;
    form.setFieldsValue({
      webhook_card_title: selectedWebhookSetting.params.card_title,
      webhook_body_template: selectedWebhookSetting.params.body_template,
      webhook_card_color: selectedWebhookSetting.params.card_color,
    });
  }, [props.open, selectedWebhookKey, form]);

  const pickNotificationParams = (values: Record<string, unknown>): NotificationParams => ({
    card_title: String(values.card_title || '').trim(),
    status: String(values.status || '').trim(),
    card_color: String(values.card_color || '').trim(),
    status_color: String(values.status_color || '').trim(),
  });

  const pickWebhookNotificationParams = (values: Record<string, unknown>): WebhookNotificationParams => ({
    card_title: String(values.webhook_card_title || '').trim(),
    body_template: String(values.webhook_body_template || '').trim(),
    card_color: String(values.webhook_card_color || '').trim(),
  });

  const mergeSelectedParams = (params: NotificationParams) =>
    settings.map((item) =>
      item.key === selectedSetting?.key
        ? {
            ...item,
            params,
            customized: JSON.stringify(params) !== JSON.stringify(item.defaults),
          }
        : item
    );

  const mergeSelectedWebhookParams = (params: WebhookNotificationParams) =>
    webhookSettings.map((item) =>
      item.key === selectedWebhookSetting?.key
        ? {
            ...item,
            params,
            customized: JSON.stringify(params) !== JSON.stringify(item.defaults),
          }
        : item
    );

  const handleValuesChange = (changed: Record<string, unknown>, values: Record<string, unknown>) => {
    const changedParam = NOTIFICATION_PARAM_FIELDS.some((field) =>
      Object.prototype.hasOwnProperty.call(changed, field)
    );
    if (changedParam && selectedSetting) {
      setSettings(mergeSelectedParams(pickNotificationParams(values)));
    }
    const changedWebhookParam = WEBHOOK_NOTIFICATION_PARAM_FIELDS.some((field) =>
      Object.prototype.hasOwnProperty.call(changed, `webhook_${field}`)
    );
    if (changedWebhookParam && selectedWebhookSetting) {
      setWebhookSettings(mergeSelectedWebhookParams(pickWebhookNotificationParams(values)));
    }
  };

  const handleResetSelected = () => {
    if (!selectedSetting) return;
    form.setFieldsValue(selectedSetting.defaults);
    setSettings(mergeSelectedParams(selectedSetting.defaults));
  };

  const handleResetSelectedWebhook = () => {
    if (!selectedWebhookSetting) return;
    form.setFieldsValue({
      webhook_card_title: selectedWebhookSetting.defaults.card_title,
      webhook_body_template: selectedWebhookSetting.defaults.body_template,
      webhook_card_color: selectedWebhookSetting.defaults.card_color,
    });
    setWebhookSettings(mergeSelectedWebhookParams(selectedWebhookSetting.defaults));
  };

  const handleSave = () => {
    form
      .validateFields()
      .then((values) => {
        const nextSettings = selectedSetting
          ? mergeSelectedParams(pickNotificationParams(values))
          : settings;
        const nextWebhookSettings = selectedWebhookSetting
          ? mergeSelectedWebhookParams(pickWebhookNotificationParams(values))
          : webhookSettings;
        const notificationPayload = nextSettings.reduce<Record<string, NotificationParams>>((acc, item) => {
          acc[item.key] = item.params;
          return acc;
        }, {});
        const webhookNotificationPayload = nextWebhookSettings.reduce<Record<string, WebhookNotificationParams>>(
          (acc, item) => {
            acc[item.key] = item.params;
            return acc;
          },
          {}
        );
        setSaving(true);
        return Promise.all([
          apiRequest('/api/settings/feishu', {
            method: 'PUT',
            body: {
              webhook_url: String(values.webhook || '').trim(),
              admin_url: String(values.admin_url || '').trim(),
            },
          }),
          apiRequest<NotificationSettingsResponse>('/api/settings/notifications', {
            method: 'PUT',
            body: { settings: notificationPayload },
          }),
          apiRequest<WebhookNotificationSettingsResponse>('/api/settings/webhook-notifications', {
            method: 'PUT',
            body: { settings: webhookNotificationPayload },
          }),
        ]);
      })
      .then(([, notificationData, webhookNotificationData]) => {
        setSettings(notificationData.items || []);
        setWebhookSettings(webhookNotificationData.items || []);
        setColorOptions(notificationData.color_options || []);
        message.success('保存成功');
      })
      .catch((err) => {
        if (err?.errorFields) return;
        message.error((err as Error).message);
      })
      .finally(() => setSaving(false));
  };

  const selectOptions = (colorOptions.length ? colorOptions : ['blue', 'green', 'yellow', 'orange', 'red', 'grey']).map(
    (item) => ({ value: item, label: item })
  );

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={920} title="通知设置">
      <Spin spinning={loading}>
        <Form layout="vertical" form={form} onValuesChange={handleValuesChange}>
          <Collapse
            className="notification-collapse"
            defaultActiveKey={['webhook', 'api']}
            items={[
              {
                key: 'webhook',
                label: 'Webhook 通知设置',
                children: (
                  <Space direction="vertical" size={16} style={{ width: '100%' }}>
                    <Form.Item
                      label="飞书 Webhook 地址"
                      name="webhook"
                      rules={[{ required: true, message: 'Webhook 不能为空' }]}
                    >
                      <Input placeholder="https://open.feishu.cn/xxx" />
                    </Form.Item>
                    <Form.Item
                      label="设备借用管理页"
                      name="admin_url"
                      rules={[{ required: true, message: '设备借用管理页不能为空' }]}
                    >
                      <Input placeholder={DEFAULT_BORROW_ADMIN_URL} />
                    </Form.Item>
                    <Table
                      rowKey="key"
                      size="small"
                      pagination={false}
                      dataSource={webhookSettings}
                      rowClassName={(record) =>
                        record.key === selectedWebhookSetting?.key ? 'notification-row-selected' : ''
                      }
                      columns={[
                        {
                          title: '触发点',
                          dataIndex: 'label',
                          render: (_: unknown, record: WebhookNotificationSettingItem) => (
                            <Space direction="vertical" size={2}>
                              <Typography.Text strong>{record.label}</Typography.Text>
                              <Typography.Text type="secondary" className="section-note">
                                {record.description}
                              </Typography.Text>
                            </Space>
                          ),
                        },
                        {
                          title: '卡片标题',
                          dataIndex: ['params', 'card_title'],
                          render: (value: string) => <Typography.Text>{value}</Typography.Text>,
                        },
                        {
                          title: '字段内容',
                          dataIndex: ['params', 'body_template'],
                          render: (value: string) => (
                            <Typography.Text className="section-note">{value.split('\n')[0] || '-'}</Typography.Text>
                          ),
                        },
                        {
                          title: '卡片颜色',
                          width: 160,
                          render: (_: unknown, record: WebhookNotificationSettingItem) => (
                            <Tag color={record.params.card_color}>{record.params.card_color}</Tag>
                          ),
                        },
                        {
                          title: '操作',
                          width: 92,
                          render: (_: unknown, record: WebhookNotificationSettingItem) => (
                            <Button
                              size="small"
                              type={record.key === selectedWebhookSetting?.key ? 'primary' : 'default'}
                              icon={<EditOutlined />}
                              onClick={() => setSelectedWebhookKey(record.key)}
                            >
                              编辑
                            </Button>
                          ),
                        },
                      ]}
                    />
                    {selectedWebhookSetting && (
                      <div className="notification-editor">
                        <Card size="small" title={`预览：${selectedWebhookSetting.label}`}>
                          <Space direction="vertical" size={8} style={{ width: '100%' }}>
                            <Space wrap>
                              <Tag color={webhookPreviewParams.card_color}>卡片 {webhookPreviewParams.card_color}</Tag>
                              {selectedWebhookSetting.customized && <Tag color="gold">已自定义</Tag>}
                            </Space>
                            <Typography.Title level={5} style={{ margin: 0 }}>
                              {webhookPreviewParams.card_title || '-'}
                            </Typography.Title>
                            <Typography.Text className="notification-template-preview">
                              {webhookPreviewParams.body_template || '-'}
                            </Typography.Text>
                            <Typography.Text>设备借用管理页：{adminUrlPreview || '-'}</Typography.Text>
                          </Space>
                        </Card>
                        <Form.Item
                          label="卡片标题"
                          name="webhook_card_title"
                          rules={[{ required: true, message: '卡片标题不能为空' }]}
                        >
                          <Input placeholder="输入 Webhook 卡片标题" />
                        </Form.Item>
                        <Form.Item
                          label="字段内容"
                          name="webhook_body_template"
                          rules={[{ required: true, message: '字段内容不能为空' }]}
                        >
                          <Input.TextArea rows={6} placeholder="每行一个卡片字段" />
                        </Form.Item>
                        <Form.Item
                          label="卡片颜色"
                          name="webhook_card_color"
                          rules={[{ required: true, message: '卡片颜色不能为空' }]}
                        >
                          <Select options={selectOptions} />
                        </Form.Item>
                        <Button icon={<ReloadOutlined />} onClick={handleResetSelectedWebhook}>
                          恢复当前触发点默认值
                        </Button>
                      </div>
                    )}
                  </Space>
                ),
              },
              {
                key: 'api',
                label: 'API 通知设置',
                children: (
                  <Space direction="vertical" size={16} style={{ width: '100%' }}>
                    <Typography.Title level={5} style={{ margin: 0 }}>
                      通知参数
                    </Typography.Title>
                    <Table
                      rowKey="key"
                      size="small"
                      pagination={false}
                      dataSource={settings}
                      rowClassName={(record) =>
                        record.key === selectedSetting?.key ? 'notification-row-selected' : ''
                      }
                      columns={[
                        {
                          title: '触发点',
                          dataIndex: 'label',
                          render: (_: unknown, record: NotificationSettingItem) => (
                            <Space direction="vertical" size={2}>
                              <Typography.Text strong>{record.label}</Typography.Text>
                              <Typography.Text type="secondary" className="section-note">
                                {record.description}
                              </Typography.Text>
                            </Space>
                          ),
                        },
                        {
                          title: '标题',
                          dataIndex: ['params', 'card_title'],
                          render: (value: string) => <Typography.Text>{value}</Typography.Text>,
                        },
                        {
                          title: '状态文案',
                          dataIndex: ['params', 'status'],
                          render: (value: string) => <Typography.Text>{value}</Typography.Text>,
                        },
                        {
                          title: '颜色',
                          render: (_: unknown, record: NotificationSettingItem) => (
                            <Space size={4}>
                              <Tag color={record.params.card_color}>卡片 {record.params.card_color}</Tag>
                              <Tag color={record.params.status_color}>状态 {record.params.status_color}</Tag>
                            </Space>
                          ),
                        },
                        {
                          title: '操作',
                          width: 92,
                          render: (_: unknown, record: NotificationSettingItem) => (
                            <Button
                              size="small"
                              type={record.key === selectedSetting?.key ? 'primary' : 'default'}
                              icon={<EditOutlined />}
                              onClick={() => setSelectedKey(record.key)}
                            >
                              编辑
                            </Button>
                          ),
                        },
                      ]}
                    />
                    {selectedSetting && (
                      <div className="notification-editor">
                        <Card size="small" title={`预览：${selectedSetting.label}`}>
                          <Space direction="vertical" size={8} style={{ width: '100%' }}>
                            <Space wrap>
                              <Tag color={previewParams.card_color}>卡片 {previewParams.card_color}</Tag>
                              <Tag color={previewParams.status_color}>状态 {previewParams.status_color}</Tag>
                              {selectedSetting.customized && <Tag color="gold">已自定义</Tag>}
                            </Space>
                            <Typography.Title level={5} style={{ margin: 0 }}>
                              {previewParams.card_title || '-'}
                            </Typography.Title>
                            <Typography.Text>{previewParams.status || '-'}</Typography.Text>
                            <Typography.Text type="secondary" className="section-note">
                              变量支持 {'{old_borrower}'} 与 {'{new_borrower}'}，仅借用人变更类通知会替换。
                            </Typography.Text>
                          </Space>
                        </Card>
                        <Form.Item
                          label="卡片标题"
                          name="card_title"
                          rules={[{ required: true, message: '卡片标题不能为空' }]}
                        >
                          <Input placeholder="输入卡片标题" />
                        </Form.Item>
                        <Form.Item
                          label="状态文案"
                          name="status"
                          rules={[{ required: true, message: '状态文案不能为空' }]}
                        >
                          <Input.TextArea rows={2} placeholder="输入状态文案" />
                        </Form.Item>
                        <Space size={12} style={{ width: '100%' }} align="start">
                          <Form.Item
                            label="卡片颜色"
                            name="card_color"
                            rules={[{ required: true, message: '卡片颜色不能为空' }]}
                            style={{ flex: 1 }}
                          >
                            <Select options={selectOptions} />
                          </Form.Item>
                          <Form.Item
                            label="状态颜色"
                            name="status_color"
                            rules={[{ required: true, message: '状态颜色不能为空' }]}
                            style={{ flex: 1 }}
                          >
                            <Select options={selectOptions} />
                          </Form.Item>
                        </Space>
                        <Button icon={<ReloadOutlined />} onClick={handleResetSelected}>
                          恢复当前触发点默认值
                        </Button>
                      </div>
                    )}
                  </Space>
                ),
              },
            ]}
          />
        </Form>
      </Spin>
      <div className="drawer-footer">
        <Button onClick={props.onCancel}>取消</Button>
        <Button type="primary" loading={saving} onClick={handleSave}>
          保存
        </Button>
      </div>
    </Drawer>
  );
}

function ModelListDrawer(props: {
  open: boolean;
  models: LLMModel[];
  testingId: number | null;
  fastModelId: number | null;
  accurateModelId: number | null;
  onClose: () => void;
  onAdd: () => void;
  onEdit: (model: LLMModel) => void;
  onDelete: (model: LLMModel) => void;
  onTest: (model: LLMModel) => void;
  onAssignFast: (model: LLMModel) => void;
  onAssignAccurate: (model: LLMModel) => void;
}) {
  return (
    <Drawer open={props.open} onClose={props.onClose} width={720} title="模型配置">
      <div className="card-stack">
        {props.models.map((model) => (
          <Card
            key={model.id}
            title={
              <Space>
                {model.name}
                {model.is_default ? <Tag color="green">默认模型</Tag> : null}
                {props.fastModelId === model.id ? <Tag color="blue">更快</Tag> : null}
                {props.accurateModelId === model.id ? <Tag color="gold">更准</Tag> : null}
              </Space>
            }
            extra={
              <Space>
                <Button
                  size="small"
                  loading={props.testingId === model.id}
                  onClick={() => props.onTest(model)}
                >
                  测试
                </Button>
                <Button size="small" onClick={() => props.onAssignFast(model)}>
                  {props.fastModelId === model.id ? '取消更快' : '指派更快'}
                </Button>
                <Button size="small" onClick={() => props.onAssignAccurate(model)}>
                  {props.accurateModelId === model.id ? '取消更准' : '指派更准'}
                </Button>
                <Button size="small" onClick={() => props.onEdit(model)}>
                  编辑
                </Button>
                <Button size="small" danger onClick={() => props.onDelete(model)}>
                  删除
                </Button>
              </Space>
            }
          >
            <Typography.Paragraph className="muted" style={{ marginBottom: 0 }}>
              类型: {model.api_type} ｜ Base URL: {model.base_url}
              <br />
              模型: {model.model} ｜ Max Tokens: {model.max_tokens}
            </Typography.Paragraph>
          </Card>
        ))}
        {!props.models.length && <Typography.Text className="muted">暂无模型配置</Typography.Text>}
      </div>
      <div className="drawer-footer">
        <Button type="primary" icon={<PlusOutlined />} onClick={props.onAdd}>
          新增模型
        </Button>
      </div>
    </Drawer>
  );
}

function ModelFormDrawer(props: {
  open: boolean;
  model?: LLMModel | null;
  onCancel: () => void;
  onSaved: (values: Record<string, unknown>, model?: LLMModel | null) => void;
}) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (!props.open) return;
    form.setFieldsValue({
      name: props.model?.name || '',
      api_type: props.model?.api_type || 'openai',
      base_url: props.model?.base_url || '',
      api_key: props.model?.api_key || '',
      model: props.model?.model || '',
      max_tokens: props.model?.max_tokens || 512,
      is_default: Boolean(props.model?.is_default),
    });
  }, [props.open, props.model, form]);

  return (
    <Drawer open={props.open} onClose={props.onCancel} width={520} title={props.model ? '编辑模型' : '新增模型'}>
      <Form layout="vertical" form={form}>
        <Form.Item
          label="名称"
          name="name"
          rules={[{ required: true, message: '名称不能为空' }]}
        >
          <Input placeholder="模型别名" />
        </Form.Item>
        <Form.Item
          label="类型"
          name="api_type"
          rules={[{ required: true, message: '类型不能为空' }]}
        >
          <Select
            options={[
              { value: 'openai', label: 'openai' },
              { value: 'openai_responses', label: 'openai_responses' },
            ]}
          />
        </Form.Item>
        <Form.Item
          label="Base URL"
          name="base_url"
          rules={[{ required: true, message: 'Base URL 不能为空' }]}
        >
          <Input placeholder="https://api.xxx.com" />
        </Form.Item>
        <Form.Item
          label="API Key"
          name="api_key"
          rules={[{ required: true, message: 'API Key 不能为空' }]}
        >
          <Input.Password placeholder="输入 API Key" />
        </Form.Item>
        <Form.Item
          label="模型"
          name="model"
          rules={[{ required: true, message: '模型不能为空' }]}
        >
          <Input placeholder="例如 gpt-4o" />
        </Form.Item>
        <Form.Item
          label="Max Tokens"
          name="max_tokens"
          rules={[{ required: true, message: 'Max Tokens 不能为空' }]}
        >
          <Input type="number" min={1} />
        </Form.Item>
        <Form.Item label="设为默认模型" name="is_default" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
      <div className="drawer-footer">
        <Button onClick={props.onCancel}>取消</Button>
        <Button
          type="primary"
          onClick={() => {
            form
              .validateFields()
              .then((values) => props.onSaved(values, props.model))
              .catch(() => null);
          }}
        >
          保存
        </Button>
      </div>
    </Drawer>
  );
}

export default function AdminApp(props: { currentUser: PortalUser }) {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [systems, setSystems] = useState<SystemItem[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [activeMenu, setActiveMenu] = useState<'devices' | 'pending' | 'records'>('devices');
  const [borrowRequests, setBorrowRequests] = useState<BorrowRequestItem[]>([]);
  const [borrowRecords, setBorrowRecords] = useState<BorrowRecord[]>([]);
  const [pendingQuery, setPendingQuery] = useState('');
  const [recordsQuery, setRecordsQuery] = useState('');
  const [pendingLoading, setPendingLoading] = useState(false);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [notifyingRecordId, setNotifyingRecordId] = useState<number | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [aiReason, setAiReason] = useState('');
  const [deviceTotal, setDeviceTotal] = useState(0);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [detailDevice, setDetailDevice] = useState<Device | null>(null);
  const [requestDetail, setRequestDetail] = useState<BorrowRequestItem | null>(null);
  const [deviceDraft, setDeviceDraft] = useState<Record<string, unknown> | null>(null);
  const [deviceDraftDevice, setDeviceDraftDevice] = useState<Device | null>(null);
  const [returnToDeviceForm, setReturnToDeviceForm] = useState(false);
  const [sortState, setSortState] = useState<{ key: string; order: SortOrder } | null>({
    key: 'status',
    order: 'ascend',
  });
  const [modelTestingId, setModelTestingId] = useState<number | null>(null);
  const [modelName, setModelName] = useState('未配置');
  const [modelLoading, setModelLoading] = useState(false);
  const [fastModelId, setFastModelId] = useState<number | null>(null);
  const [accurateModelId, setAccurateModelId] = useState<number | null>(null);
  const [fastModelName, setFastModelName] = useState('未配置');
  const [accurateModelName, setAccurateModelName] = useState('未配置');
  const [assignmentsReady, setAssignmentsReady] = useState(false);
  const [devicePage, setDevicePage] = useState(1);
  const [aiMode, setAiMode] = useState<'fast' | 'accurate' | null>(() => {
    const stored = localStorage.getItem('ai_search_mode');
    if (stored === 'fast' || stored === 'accurate') {
      return stored;
    }
    return null;
  });
  const performanceOrder: Record<string, number> = {
    强劲: 0,
    较高: 1,
    一般: 2,
    较低: 3,
  };
  const getPerformanceRank = (notes?: string | null) => {
    const value = extractPerformance(notes);
    return performanceOrder[value] ?? 99;
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [vendorRes, systemRes, deviceRes] = await Promise.all([
        apiRequest<{ items: Vendor[] }>('/api/vendors'),
        apiRequest<{ items: SystemItem[] }>('/api/systems?include_versions=1'),
        apiRequest<{ items: Device[] }>('/api/devices'),
      ]);
      setVendors(vendorRes.items || []);
      setSystems(systemRes.items || []);
      setDevices(deviceRes.items || []);
      setDeviceTotal(deviceRes.items?.length || 0);
      setAiReason('');
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadDevices = async (q?: string) => {
    setLoading(true);
    try {
      const url = q ? `/api/devices?query=${encodeURIComponent(q)}` : '/api/devices';
      const deviceRes = await apiRequest<{ items: Device[] }>(url);
      setDevices(deviceRes.items || []);
      if (!q) {
        setAiReason('');
        setDeviceTotal(deviceRes.items?.length || 0);
      }
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadBorrowRequests = async (q?: string) => {
    setPendingLoading(true);
    try {
      const url = q ? `/api/borrow-requests?query=${encodeURIComponent(q)}` : '/api/borrow-requests';
      const res = await apiRequest<{ items: BorrowRequestItem[] }>(url);
      setBorrowRequests(res.items || []);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setPendingLoading(false);
    }
  };

  const refreshPendingCount = async () => {
    try {
      const res = await apiRequest<{ items: BorrowRequestItem[] }>('/api/borrow-requests?status=pending');
      setPendingCount(res.items?.length || 0);
    } catch {
      // avoid spamming toast for background refresh
    }
  };

  const loadBorrowRecords = async (q?: string) => {
    setRecordsLoading(true);
    try {
      const url = q ? `/api/borrow-records?query=${encodeURIComponent(q)}` : '/api/borrow-records';
      const res = await apiRequest<{ items: BorrowRecord[] }>(url);
      setBorrowRecords(res.items || []);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setRecordsLoading(false);
    }
  };

  const handleExportBorrowData = async () => {
    try {
      const url = query.trim()
        ? `/api/devices/export?query=${encodeURIComponent(query.trim())}`
        : '/api/devices/export';
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`导出失败: ${res.status}`);
      }
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'borrow_data.xlsx';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
      message.success('导出成功');
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const updateModelName = (items: LLMModel[]) => {
    const current = items.find((item) => Boolean(item.is_default)) || items[0];
    if (current) {
      setModelName(current.name || current.model || '未配置');
    } else {
      setModelName('未配置');
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

  const loadModels = async () => {
    setModelLoading(true);
    try {
      const [modelRes, assignmentRes] = await Promise.all([
        apiRequest<{ items: LLMModel[] }>('/api/llm/models'),
        apiRequest<LLMModelAssignments>('/api/llm/models/assignments'),
      ]);
      setModels(modelRes.items || []);
      updateModelName(modelRes.items || []);
      applyAssignments(modelRes.items || [], assignmentRes);
    } catch (err) {
      message.error((err as Error).message);
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

  const loadModelName = async () => {
    setModelLoading(true);
    try {
      const [modelRes, assignmentRes] = await Promise.all([
        apiRequest<{ items: LLMModel[] }>('/api/llm/models'),
        apiRequest<LLMModelAssignments>('/api/llm/models/assignments'),
      ]);
      updateModelName(modelRes.items || []);
      applyAssignments(modelRes.items || [], assignmentRes);
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
    loadData();
    loadModelName();
    refreshPendingCount();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      refreshPendingCount();
    }, 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (activeMenu === 'pending') {
      loadBorrowRequests(pendingQuery.trim() || undefined);
    }
    if (activeMenu === 'records') {
      loadBorrowRecords(recordsQuery.trim() || undefined);
    }
  }, [activeMenu]);

  useEffect(() => {
    if (activeMenu !== 'pending') return;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      loadBorrowRequests(pendingQuery.trim() || undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeMenu, pendingQuery]);

  const openDrawer = (state: DrawerState) => setDrawer(state);
  const closeDrawer = () => setDrawer(null);
  const resetDeviceDraft = () => {
    setDeviceDraft(null);
    setDeviceDraftDevice(null);
    setReturnToDeviceForm(false);
  };
  const reopenDeviceForm = () => {
    setReturnToDeviceForm(false);
    openDrawer({ type: 'device-form', payload: deviceDraftDevice || undefined });
  };
  const returnToDeviceFormIfNeeded = () => {
    if (!returnToDeviceForm) return false;
    reopenDeviceForm();
    return true;
  };

  const currentDevice =
    drawer?.type === 'device-form' || drawer?.type === 'device-delete' || drawer?.type === 'device-return'
      ? ((drawer.payload as Device) || null)
      : null;

  const currentVendor =
    drawer?.type === 'vendor-form' ||
    drawer?.type === 'vendor-delete' ||
    drawer?.type === 'vendor-rebind'
      ? ((drawer.payload as Vendor) || null)
      : null;

  const versionPayload =
    drawer?.type === 'version-rebind' || drawer?.type === 'version-delete'
      ? (drawer.payload as VersionPayload)
      : null;

  const currentSystem =
    drawer?.type === 'system-form' ||
    drawer?.type === 'system-delete' ||
    drawer?.type === 'system-rebind' ||
    drawer?.type === 'version-form'
      ? ((drawer.payload as SystemItem) || null)
      : versionPayload?.system || null;

  const currentVersion = versionPayload?.version || null;

  const currentModel =
    drawer?.type === 'model-form' || drawer?.type === 'model-delete'
      ? ((drawer.payload as LLMModel) || null)
      : null;

  const deviceColumns = [
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
      onHeaderCell: () => ({ className: 'compact-header' }),
      render: (value: string) => <Tag color={value === '正常' ? 'green' : 'volcano'}>{value}</Tag>,
    },
    {
      title: '设备类型',
      dataIndex: 'type',
      key: 'type',
      sorter: (a: Device, b: Device) => (a.type || '').localeCompare(b.type || ''),
      sortOrder: sortState?.key === 'type' ? sortState.order : null,
      onHeaderCell: () => ({ className: 'compact-header' }),
      render: (value: string | null) => renderDeviceType(value),
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
      title: '借用人',
      dataIndex: 'borrower_name',
      key: 'borrower_name',
      align: 'center' as const,
      render: (_: string | null, record: Device) => <PersonDisplay person={personFromBorrower(record)} size="small" />,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: Device) => (
        <Space wrap size={[6, 6]}>
          <Button size="small" onClick={() => setDetailDevice(record)}>
            详情
          </Button>
          <Button
            size="small"
            onClick={() => {
              setDeviceDraft(null);
              setReturnToDeviceForm(false);
              setDeviceDraftDevice(record);
              openDrawer({ type: 'device-form', payload: record });
            }}
          >
            编辑
          </Button>
          <Button
            size="small"
            icon={<RollbackOutlined />}
            onClick={() => openDrawer({ type: 'device-return', payload: record })}
          >
            归还
          </Button>
        </Space>
      ),
    },
  ];

  const handleApproveRequest = async (record: BorrowRequestItem) => {
    try {
      const res = await apiRequest<{ message?: string }>(`/api/borrow-requests/${record.id}/approve`, {
        method: 'POST',
      });
      message.success(res.message || (record.request_type === 'change' ? '借用人变更成功' : '确认借出成功'));
      await Promise.all([
        loadBorrowRequests(pendingQuery.trim() || undefined),
        loadDevices(query.trim() || undefined),
        loadBorrowRecords(recordsQuery.trim() || undefined),
        refreshPendingCount(),
      ]);
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const handleCancelRequest = async (record: BorrowRequestItem) => {
    try {
      await apiRequest(`/api/borrow-requests/${record.id}/cancel`, { method: 'POST' });
      message.success('取消成功');
      await Promise.all([
        loadBorrowRequests(pendingQuery.trim() || undefined),
        loadDevices(query.trim() || undefined),
        refreshPendingCount(),
      ]);
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const canTriggerOverdueNotification = (record: BorrowRecord) => {
    if (record.status !== 'borrowed' || !record.expected_return_at) {
      return false;
    }
    const expectedAt = Date.parse(record.expected_return_at);
    return Number.isFinite(expectedAt) && expectedAt < Date.now();
  };

  const handleTriggerOverdueNotification = async (record: BorrowRecord) => {
    setNotifyingRecordId(record.id);
    try {
      const res = await apiRequest<{ message?: string }>(
        `/api/borrow-records/${record.id}/overdue-notification`,
        { method: 'POST' }
      );
      message.success(res.message || '逾期通知已发送');
      await loadBorrowRecords(recordsQuery.trim() || undefined);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setNotifyingRecordId(null);
    }
  };

  const pendingColumns = [
    {
      title: '类型',
      dataIndex: 'request_type',
      key: 'request_type',
      render: (value: string) =>
        value === 'change' ? <Tag color="purple">借用变更</Tag> : <Tag color="blue">借用</Tag>,
    },
    {
      title: '申请人',
      dataIndex: 'borrower_name',
      key: 'borrower_name',
      align: 'center' as const,
      render: (_: string, record: BorrowRequestItem) => (
        <PersonDisplay person={personFromBorrower(record)} size="small" />
      ),
    },
    { title: '设备型号', dataIndex: 'device_model', key: 'device_model' },
    {
      title: '申请时间',
      dataIndex: 'requested_at',
      key: 'requested_at',
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '借用状态',
      key: 'borrow_status',
      render: (_: unknown, record: BorrowRequestItem) => {
        if (record.request_status === 'approved') {
          return <Tag color="green">已确认</Tag>;
        }
        if (record.request_status === 'cancelled' || record.request_status === 'canceled') {
          return <Tag color="volcano">已取消</Tag>;
        }
        return <Tag color="gold">待处理</Tag>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: BorrowRequestItem) => {
        const isPending = record.request_status === 'pending';
        return (
          <Space wrap>
            <Button size="small" onClick={() => setRequestDetail(record)}>
              详情
            </Button>
            <Button
              size="small"
              onClick={() => {
                const deviceQuery = String(record.device_model || '').trim();
                setActiveMenu('devices');
                setQuery(deviceQuery);
                setAiReason('');
                setDevicePage(1);
                loadDevices(deviceQuery);
              }}
            >
              设备
            </Button>
            <Button size="small" type="primary" disabled={!isPending} onClick={() => handleApproveRequest(record)}>
              确认
            </Button>
            <Button size="small" danger disabled={!isPending} onClick={() => handleCancelRequest(record)}>
              取消
            </Button>
          </Space>
        );
      },
    },
  ];

  const recordColumns = [
    {
      title: '借用人',
      dataIndex: 'borrower_name',
      key: 'borrower_name',
      align: 'center' as const,
      render: (_: string, record: BorrowRecord) => <PersonDisplay person={personFromBorrower(record)} size="small" />,
    },
    {
      title: '借用人变更',
      key: 'borrower_changes',
      render: (_: unknown, record: BorrowRecord) => {
        const changes = record.borrower_changes || [];
        if (!changes.length) {
          return '-';
        }
        return (
          <Space direction="vertical" size={2}>
            {changes.map((change, index) => (
              <div key={change.id ?? index} className="borrower-change-row">
                <PersonDisplay person={personFromChange(change, 'before')} size="tiny" />
                <span className="borrower-change-arrow">→</span>
                <PersonDisplay person={personFromChange(change, 'after')} size="tiny" />
                <div className="muted">{formatDateTime(change.changed_at)}</div>
              </div>
            ))}
          </Space>
        );
      },
    },
    { title: '设备型号', dataIndex: 'device_model', key: 'device_model' },
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
      render: (value: string | null, record: BorrowRecord) => {
        const canNotify = canTriggerOverdueNotification(record);
        const hasManualSent = Boolean(record.overdue_manual_sent_at);
        return (
          <Space direction="vertical" size={4} className="record-return-cell">
            <span>{formatDateTime(value || undefined)}</span>
            <Button
              size="small"
              icon={<BellOutlined />}
              disabled={!canNotify}
              loading={notifyingRecordId === record.id}
              type={canNotify && !hasManualSent ? 'primary' : 'default'}
              onClick={() => handleTriggerOverdueNotification(record)}
            >
              {hasManualSent ? '再通知' : '通知'}
            </Button>
            <Tag color={hasManualSent ? 'green' : canNotify ? 'gold' : 'default'} className="record-notify-tag">
              {hasManualSent ? '已主动触发' : canNotify ? '未主动触发' : '不可触发'}
            </Tag>
          </Space>
        );
      },
    },
    {
      title: '归还时间',
      dataIndex: 'returned_at',
      key: 'returned_at',
      render: (value: string | null) => formatDateTime(value || undefined),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (value: string) =>
        value === 'returned' ? <Tag color="default">已归还</Tag> : <Tag color="green">借用中</Tag>,
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
    <App>
      <Layout className="app-layout">
        <Layout.Header className="app-header">
          <div className="app-header-content">
            <Space direction="vertical" size={2}>
              <Typography.Title level={4} style={{ margin: 0 }}>
                设备借用助手 · 管理页
              </Typography.Title>
              <Typography.Text type="secondary">
                统一管理设备与配置，支持借用、归还与通知。
              </Typography.Text>
            </Space>
            <div className="toolbar">
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  resetDeviceDraft();
                  openDrawer({ type: 'device-form' });
                }}
              >
                添加设备
              </Button>
              <Button
                icon={<SettingOutlined />}
                onClick={() => {
                  setReturnToDeviceForm(false);
                  openDrawer({ type: 'vendor-list' });
                }}
              >
                厂商配置
              </Button>
              <Button
                icon={<SettingOutlined />}
                onClick={() => {
                  setReturnToDeviceForm(false);
                  openDrawer({ type: 'system-list' });
                }}
              >
                系统配置
              </Button>
              <Button icon={<SettingOutlined />} onClick={() => openDrawer({ type: 'notify' })}>
                通知设置
              </Button>
              <Button
                icon={<DatabaseOutlined />}
                onClick={() => {
                  openDrawer({ type: 'model-list' });
                  loadModels();
                }}
              >
                模型配置
              </Button>
              <Button
                icon={<ExportOutlined />}
                onClick={() => window.open('/borrow', '_blank', 'noopener,noreferrer')}
              >
                打开借用页
              </Button>
            </div>
          </div>
        </Layout.Header>
        <div className="app-body-with-sider">
          <aside className="app-sider">
            <Menu
              mode="inline"
              theme="light"
              selectedKeys={[activeMenu]}
              onClick={(info) => setActiveMenu(info.key as 'devices' | 'pending' | 'records')}
              items={[
                { key: 'devices', icon: <AppstoreOutlined />, label: '设备' },
                {
                  key: 'pending',
                  icon: <ClockCircleOutlined />,
                  label: (
                    <span className="menu-item-label">
                      <span>待处理</span>
                      <Badge count={pendingCount} size="small" showZero={false} />
                    </span>
                  ),
                },
                { key: 'records', icon: <ProfileOutlined />, label: '借用记录' },
              ]}
            />
            <div className="sider-current-user">
              <PersonDisplay person={props.currentUser} size="medium" showJobTitle />
            </div>
          </aside>
          <main className="app-content app-content-with-sider">
            <div className="page page-with-sider">
              {activeMenu === 'devices' ? (
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
                          setAiReason('');
                          setDevicePage(1);
                          loadDevices(query.trim());
                        }}
                        disabled={aiLoading}
                      >
                        搜索
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
                              setDevices(data.items || []);
                              setAiReason(data.ai_reason || '');
                              setDevicePage(1);
                              if (!data.items?.length) {
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
                      <Button onClick={handleExportBorrowData}>导出借用数据</Button>
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
                    columns={deviceColumns}
                    pagination={{ pageSize: 20, current: devicePage }}
                    tableLayout="auto"
                    size="small"
                    className="full-table full-table-compact full-table-auto"
                    sortDirections={['ascend', 'descend']}
                    sticky={{
                      offsetHeader: 0,
                      getContainer: () => document.querySelector('.app-content-with-sider') as HTMLElement,
                    }}
                    loading={loading}
                    onChange={(pagination, __, sorter, extra) => {
                      if (extra?.action === 'paginate') {
                        setDevicePage(pagination.current || 1);
                        return;
                      }
                      if (extra?.action === 'sort') {
                        const { columnKey, order } = normalizeSorter(sorter);
                        if (!columnKey) return;
                        const nextOrder: SortOrder =
                          order ||
                          (sortState?.key === columnKey && sortState.order === 'ascend' ? 'descend' : 'ascend');
                        setSortState({ key: columnKey, order: nextOrder });
                        setDevicePage(1);
                      }
                    }}
                  />
                </section>
              ) : null}

              {activeMenu === 'pending' ? (
                <section className="table-card">
                  <div className="table-header">
                    <div className="table-actions">
                      <Input
                        value={pendingQuery}
                        onChange={(event) => setPendingQuery(event.target.value)}
                        placeholder="搜索通知内容"
                        style={{ width: 280 }}
                        allowClear
                      />
                      <Button
                        icon={<SearchOutlined />}
                        onClick={() => loadBorrowRequests(pendingQuery.trim() || undefined)}
                      >
                        搜索
                      </Button>
                      <Button
                        icon={<ReloadOutlined />}
                        onClick={() => {
                          setPendingQuery('');
                          loadBorrowRequests();
                        }}
                      >
                        清除
                      </Button>
                    </div>
                    <Space>{pendingLoading ? <Spin size="small" /> : null}</Space>
                  </div>
                  <Table
                    rowKey="id"
                    dataSource={borrowRequests}
                    columns={pendingColumns}
                    pagination={{ pageSize: 20 }}
                    tableLayout="fixed"
                    size="small"
                    className="full-table full-table-compact"
                    sticky={{
                      offsetHeader: 0,
                      getContainer: () => document.querySelector('.app-content-with-sider') as HTMLElement,
                    }}
                    loading={pendingLoading}
                  />
                </section>
              ) : null}

              {activeMenu === 'records' ? (
                <section className="table-card">
                  <div className="table-header">
                    <div className="table-actions">
                      <Input
                        value={recordsQuery}
                        onChange={(event) => setRecordsQuery(event.target.value)}
                        placeholder="搜索借用记录"
                        style={{ width: 280 }}
                        allowClear
                      />
                      <Button
                        icon={<SearchOutlined />}
                        onClick={() => loadBorrowRecords(recordsQuery.trim() || undefined)}
                      >
                        搜索
                      </Button>
                      <Button
                        icon={<ReloadOutlined />}
                        onClick={() => {
                          setRecordsQuery('');
                          loadBorrowRecords();
                        }}
                      >
                        清除
                      </Button>
                    </div>
                    <Space>{recordsLoading ? <Spin size="small" /> : null}</Space>
                  </div>
                  <Table
                    rowKey="id"
                    dataSource={borrowRecords}
                    columns={recordColumns}
                    pagination={{ pageSize: 20 }}
                    tableLayout="fixed"
                    size="small"
                    className="full-table full-table-compact"
                    sticky={{
                      offsetHeader: 0,
                      getContainer: () => document.querySelector('.app-content-with-sider') as HTMLElement,
                    }}
                    loading={recordsLoading}
                  />
                </section>
              ) : null}
            </div>
          </main>
        </div>
      </Layout>

      <DeviceFormDrawer
        open={drawer?.type === 'device-form'}
        device={currentDevice}
        draft={deviceDraft}
        vendors={vendors}
        systems={systems}
        onCancel={() => {
          resetDeviceDraft();
          closeDrawer();
        }}
        onDelete={(device) => openDrawer({ type: 'device-delete', payload: device })}
        onSaved={async (values, device) => {
          const payload = {
            model: String(values.model || '').trim(),
            status: String(values.status || '').trim(),
            type: values.type || null,
            vendor_id: values.vendor_id,
            system_id: values.system_id,
            system_version_id: values.system_version_id,
            resolution: values.resolution || null,
            arch: values.arch || null,
            cpu: values.cpu || null,
            boot_password: values.boot_password || null,
            notes: values.notes || null,
          };
          if (!payload.model || !payload.status || !payload.vendor_id || !payload.system_id || !payload.system_version_id) {
            message.error('请填写关键字段');
            return;
          }
          try {
            if (device) {
              await apiRequest(`/api/devices/${device.id}`, { method: 'PUT', body: payload });
              message.success('更新成功');
            } else {
              await apiRequest('/api/devices', { method: 'POST', body: payload });
              message.success('新增成功');
            }
            resetDeviceDraft();
            closeDrawer();
            loadData();
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
        onAddVendor={(draft, device) => {
          setDeviceDraft(draft);
          setDeviceDraftDevice(device || null);
          setReturnToDeviceForm(true);
          openDrawer({ type: 'vendor-form' });
        }}
        onAddSystem={(draft, device) => {
          setDeviceDraft(draft);
          setDeviceDraftDevice(device || null);
          setReturnToDeviceForm(true);
          openDrawer({ type: 'system-form' });
        }}
        onAddVersion={(draft, system, device) => {
          setDeviceDraft(draft);
          setDeviceDraftDevice(device || null);
          setReturnToDeviceForm(true);
          openDrawer({ type: 'version-form', payload: system });
        }}
      />

      <VendorListDrawer
        open={drawer?.type === 'vendor-list'}
        vendors={vendors}
        onClose={closeDrawer}
        onAdd={() => openDrawer({ type: 'vendor-form' })}
        onEdit={(vendor) => openDrawer({ type: 'vendor-form', payload: vendor })}
        onDelete={(vendor) => openDrawer({ type: 'vendor-delete', payload: vendor })}
      />

      <VendorFormDrawer
        open={drawer?.type === 'vendor-form'}
        vendor={currentVendor}
        vendors={vendors}
        onCancel={() => {
          if (!returnToDeviceFormIfNeeded()) {
            openDrawer({ type: 'vendor-list' });
          }
        }}
        onSaved={async (name, vendor) => {
          try {
            if (vendor) {
              await apiRequest(`/api/vendors/${vendor.id}`, { method: 'PUT', body: { name } });
              message.success('更新成功');
            } else {
              await apiRequest('/api/vendors', { method: 'POST', body: { name } });
              message.success('新增成功');
            }
            loadData();
            if (!returnToDeviceFormIfNeeded()) {
              openDrawer({ type: 'vendor-list' });
            }
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />

      <VendorRebindDrawer
        open={drawer?.type === 'vendor-rebind'}
        vendor={currentVendor}
        vendors={vendors}
        onCancel={() => openDrawer({ type: 'vendor-list' })}
        onConfirm={async (targetId) => {
          if (!currentVendor) return;
          try {
            await apiRequest(`/api/vendors/${currentVendor.id}`, {
              method: 'DELETE',
              body: { rebind_vendor_id: targetId },
            });
            message.success('删除成功');
            loadData();
            openDrawer({ type: 'vendor-list' });
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />

      <SystemListDrawer
        open={drawer?.type === 'system-list'}
        systems={systems}
        onClose={closeDrawer}
        onAddSystem={() => openDrawer({ type: 'system-form' })}
        onEditSystem={(system) => openDrawer({ type: 'system-form', payload: system })}
        onDeleteSystem={(system) => openDrawer({ type: 'system-delete', payload: system })}
        onAddVersion={(system) => openDrawer({ type: 'version-form', payload: system })}
        onDeleteVersion={(system, version) =>
          openDrawer({ type: 'version-delete', payload: { system, version } })
        }
      />

      <SystemFormDrawer
        open={drawer?.type === 'system-form'}
        system={currentSystem}
        systems={systems}
        onCancel={() => {
          if (!returnToDeviceFormIfNeeded()) {
            openDrawer({ type: 'system-list' });
          }
        }}
        onSaved={async (name, system) => {
          try {
            if (system) {
              await apiRequest(`/api/systems/${system.id}`, { method: 'PUT', body: { name } });
              message.success('更新成功');
            } else {
              await apiRequest('/api/systems', { method: 'POST', body: { name } });
              message.success('新增成功');
            }
            loadData();
            if (!returnToDeviceFormIfNeeded()) {
              openDrawer({ type: 'system-list' });
            }
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />

      <VersionFormDrawer
        open={drawer?.type === 'version-form'}
        system={currentSystem}
        onCancel={() => {
          if (!returnToDeviceFormIfNeeded()) {
            openDrawer({ type: 'system-list' });
          }
        }}
        onSaved={async (version, system) => {
          try {
            await apiRequest(`/api/systems/${system.id}/versions`, { method: 'POST', body: { version } });
            message.success('新增成功');
            loadData();
            if (!returnToDeviceFormIfNeeded()) {
              openDrawer({ type: 'system-list' });
            }
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />

      <SystemRebindDrawer
        open={drawer?.type === 'system-rebind'}
        system={currentSystem}
        systems={systems}
        onCancel={() => openDrawer({ type: 'system-list' })}
        onConfirm={async (systemId, versionId) => {
          if (!currentSystem) return;
          try {
            await apiRequest(`/api/systems/${currentSystem.id}`, {
              method: 'DELETE',
              body: { rebind_system_id: systemId, rebind_version_id: versionId },
            });
            message.success('删除成功');
            loadData();
            openDrawer({ type: 'system-list' });
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />

      <VersionRebindDrawer
        open={drawer?.type === 'version-rebind'}
        system={currentSystem}
        version={currentVersion}
        onCancel={() => openDrawer({ type: 'system-list' })}
        onConfirm={async (versionId) => {
          if (!currentVersion) return;
          try {
            await apiRequest(`/api/versions/${currentVersion.id}`, {
              method: 'DELETE',
              body: { rebind_version_id: versionId },
            });
            message.success('删除成功');
            loadData();
            openDrawer({ type: 'system-list' });
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />

      <NotifyDrawer open={drawer?.type === 'notify'} onCancel={closeDrawer} />

      <ModelListDrawer
        open={drawer?.type === 'model-list'}
        models={models}
        testingId={modelTestingId}
        fastModelId={fastModelId}
        accurateModelId={accurateModelId}
        onClose={closeDrawer}
        onAdd={() => openDrawer({ type: 'model-form' })}
        onEdit={(model) => openDrawer({ type: 'model-form', payload: model })}
        onDelete={(model) => openDrawer({ type: 'model-delete', payload: model })}
        onTest={async (model) => {
          if (modelTestingId) {
            return;
          }
          setModelTestingId(model.id);
          try {
            await apiRequest(`/api/llm/models/${model.id}/test`, { method: 'POST' });
            message.success('模型可用');
          } catch (err) {
            message.error((err as Error).message);
          } finally {
            setModelTestingId(null);
          }
        }}
        onAssignFast={async (model) => {
          if (fastModelId === model.id) {
            try {
              await apiRequest('/api/llm/models/assignments/fast', { method: 'DELETE' });
              message.success('已取消更快指派');
              loadModels();
            } catch (err) {
              message.error((err as Error).message);
            }
            return;
          }
          if (fastModelId && fastModelId !== model.id) {
            message.warning(`已指派更快模型: ${fastModelName}，请先取消指派`);
            return;
          }
          try {
            await apiRequest(`/api/llm/models/${model.id}/assign`, { method: 'POST', body: { role: 'fast' } });
            message.success('指派更快成功');
            loadModels();
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
        onAssignAccurate={async (model) => {
          if (accurateModelId === model.id) {
            try {
              await apiRequest('/api/llm/models/assignments/accurate', { method: 'DELETE' });
              message.success('已取消更准指派');
              loadModels();
            } catch (err) {
              message.error((err as Error).message);
            }
            return;
          }
          if (accurateModelId && accurateModelId !== model.id) {
            message.warning(`已指派更准模型: ${accurateModelName}，请先取消指派`);
            return;
          }
          try {
            await apiRequest(`/api/llm/models/${model.id}/assign`, { method: 'POST', body: { role: 'accurate' } });
            message.success('指派更准成功');
            loadModels();
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />

      <ModelFormDrawer
        open={drawer?.type === 'model-form'}
        model={currentModel}
        onCancel={() => openDrawer({ type: 'model-list' })}
        onSaved={async (values, model) => {
          const payload = {
            name: String(values.name || '').trim(),
            api_type: values.api_type,
            base_url: String(values.base_url || '').trim(),
            api_key: String(values.api_key || '').trim(),
            model: String(values.model || '').trim(),
            max_tokens: Number(values.max_tokens || 0),
            is_default: Boolean(values.is_default),
          };
          if (!payload.name || !payload.base_url || !payload.api_key || !payload.model || !payload.max_tokens) {
            message.error('请填写完整模型信息');
            return;
          }
          try {
            if (model) {
              await apiRequest(`/api/llm/models/${model.id}`, { method: 'PUT', body: payload });
              message.success('更新成功');
            } else {
              await apiRequest('/api/llm/models', { method: 'POST', body: payload });
              message.success('新增成功');
            }
            loadModels();
            openDrawer({ type: 'model-list' });
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

      <Drawer
        open={Boolean(requestDetail)}
        onClose={() => setRequestDetail(null)}
        width={420}
        title={`申请详情 ${requestDetail ? `#${requestDetail.id}` : ''}`}
      >
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Typography.Text strong>类型</Typography.Text>
          <Typography.Text>{requestDetail?.request_type === 'change' ? '借用变更' : '借用'}</Typography.Text>
          <Typography.Text strong>申请人</Typography.Text>
          <PersonDisplay person={requestDetail ? personFromBorrower(requestDetail) : null} size="medium" />
          <Typography.Text strong>设备型号</Typography.Text>
          <Typography.Text>{requestDetail?.device_model || '-'}</Typography.Text>
          <Typography.Text strong>申请时间</Typography.Text>
          <Typography.Text>{formatDateTime(requestDetail?.requested_at)}</Typography.Text>
          <Typography.Text strong>预计归还时间</Typography.Text>
          <Typography.Text>{formatDateTime(requestDetail?.expected_return_at)}</Typography.Text>
          <Typography.Text strong>设备状态</Typography.Text>
          <Typography.Text>{requestDetail?.device_status || '-'}</Typography.Text>
          <Typography.Text strong>设备类型</Typography.Text>
          <div>{renderDeviceType(requestDetail?.device_type || null)}</div>
          <Typography.Text strong>厂商</Typography.Text>
          <Typography.Text>{requestDetail?.vendor_name || '-'}</Typography.Text>
          <Typography.Text strong>系统</Typography.Text>
          <Typography.Text>{requestDetail?.system_name || '-'}</Typography.Text>
          <Typography.Text strong>系统版本</Typography.Text>
          <Typography.Text>{requestDetail?.system_version || '-'}</Typography.Text>
          <Typography.Text strong>分辨率</Typography.Text>
          <Typography.Text>{requestDetail?.resolution || '-'}</Typography.Text>
          <Typography.Text strong>架构</Typography.Text>
          <Typography.Text>{requestDetail?.arch || '-'}</Typography.Text>
          <Typography.Text strong>CPU型号</Typography.Text>
          <Typography.Text>{requestDetail?.cpu || '-'}</Typography.Text>
          <Typography.Text strong>开机密码</Typography.Text>
          <Typography.Text>{requestDetail?.boot_password || '-'}</Typography.Text>
          <Typography.Text strong>备注</Typography.Text>
          <Typography.Text>{requestDetail?.notes || '-'}</Typography.Text>
        </Space>
      </Drawer>

      <ConfirmDrawer
        open={drawer?.type === 'device-delete'}
        title="删除设备"
        description={`确认删除设备 ${currentDevice?.model || ''} (ID: ${currentDevice?.id || '-'}) 吗？`}
        confirmText="确认删除"
        danger
        onCancel={() => openDrawer({ type: 'device-form', payload: currentDevice })}
        onConfirm={async () => {
          if (!currentDevice) return;
          try {
            await apiRequest(`/api/devices/${currentDevice.id}`, { method: 'DELETE' });
            message.success('删除成功');
            closeDrawer();
            loadData();
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />

      <ConfirmDrawer
        open={drawer?.type === 'device-return'}
        title="归还设备"
        description={`确认归还设备 ${currentDevice?.model || ''} (ID: ${currentDevice?.id || '-'}) 吗？`}
        confirmText="确认归还"
        onCancel={closeDrawer}
        onConfirm={async () => {
          if (!currentDevice) return;
          try {
            await apiRequest(`/api/devices/${currentDevice.id}/return`, { method: 'POST' });
            message.success('归还成功');
            closeDrawer();
            loadData();
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />

      <ConfirmDrawer
        open={drawer?.type === 'vendor-delete'}
        title="删除厂商"
        description={`确认删除厂商 ${currentVendor?.name || ''} 吗？`}
        confirmText="确认删除"
        danger
        onCancel={() => openDrawer({ type: 'vendor-list' })}
        onConfirm={async () => {
          if (!currentVendor) return;
          try {
            await apiRequest(`/api/vendors/${currentVendor.id}`, {
              method: 'DELETE',
              body: { rebind_vendor_id: null },
            });
            message.success('删除成功');
            loadData();
            openDrawer({ type: 'vendor-list' });
          } catch (err) {
            const msg = (err as Error).message;
            if (msg.includes('重新绑定')) {
              openDrawer({ type: 'vendor-rebind', payload: currentVendor });
            } else {
              message.error(msg);
            }
          }
        }}
      />

      <ConfirmDrawer
        open={drawer?.type === 'system-delete'}
        title="删除系统"
        description={`确认删除系统 ${currentSystem?.name || ''} 吗？`}
        confirmText="确认删除"
        danger
        onCancel={() => openDrawer({ type: 'system-list' })}
        onConfirm={async () => {
          if (!currentSystem) return;
          try {
            await apiRequest(`/api/systems/${currentSystem.id}`, {
              method: 'DELETE',
              body: { rebind_system_id: null, rebind_version_id: null },
            });
            message.success('删除成功');
            loadData();
            openDrawer({ type: 'system-list' });
          } catch (err) {
            const msg = (err as Error).message;
            if (msg.includes('重新绑定')) {
              openDrawer({ type: 'system-rebind', payload: currentSystem });
            } else {
              message.error(msg);
            }
          }
        }}
      />

      <ConfirmDrawer
        open={drawer?.type === 'version-delete'}
        title="删除版本"
        description={`确认删除版本 ${currentVersion?.version || ''} 吗？`}
        confirmText="确认删除"
        danger
        onCancel={() => openDrawer({ type: 'system-list' })}
        onConfirm={async () => {
          if (!currentVersion) return;
          try {
            await apiRequest(`/api/versions/${currentVersion.id}`, {
              method: 'DELETE',
              body: { rebind_version_id: null },
            });
            message.success('删除成功');
            loadData();
            openDrawer({ type: 'system-list' });
          } catch (err) {
            const msg = (err as Error).message;
            if (msg.includes('重新绑定')) {
              if (currentSystem && currentVersion) {
                openDrawer({ type: 'version-rebind', payload: { system: currentSystem, version: currentVersion } });
              }
            } else {
              message.error(msg);
            }
          }
        }}
      />

      <ConfirmDrawer
        open={drawer?.type === 'model-delete'}
        title="删除模型"
        description={`确认删除模型 ${currentModel?.name || ''} 吗？`}
        confirmText="确认删除"
        danger
        onCancel={() => openDrawer({ type: 'model-list' })}
        onConfirm={async () => {
          if (!currentModel) return;
          try {
            await apiRequest(`/api/llm/models/${currentModel.id}`, { method: 'DELETE' });
            message.success('删除成功');
            loadModels();
            openDrawer({ type: 'model-list' });
          } catch (err) {
            message.error((err as Error).message);
          }
        }}
      />
    </App>
  );
}
