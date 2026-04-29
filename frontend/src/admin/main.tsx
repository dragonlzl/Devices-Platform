import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, Result, Spin, message } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
import 'antd/dist/reset.css';
import '../shared/styles.css';
import { appTheme } from '../shared/theme';
import AdminApp from './AdminApp';
import { migrateCurrentUserBorrowerData, requirePortalSession } from '../shared/auth';

message.config({ duration: 3 });
dayjs.locale('zh-cn');

const root = ReactDOM.createRoot(document.getElementById('root')!);

function renderWithProvider(children: React.ReactNode) {
  root.render(
    <React.StrictMode>
      <ConfigProvider theme={appTheme} locale={zhCN}>
        {children}
      </ConfigProvider>
    </React.StrictMode>
  );
}

renderWithProvider(
  <div className="auth-loading">
    <Spin />
    <span>登录检测中...</span>
  </div>
);

async function bootstrap() {
  try {
    const session = await requirePortalSession();
    await migrateCurrentUserBorrowerData();
    renderWithProvider(<AdminApp currentUser={session.user} />);
  } catch (err) {
    renderWithProvider(
      <Result
        status="warning"
        title="登录检测失败"
        subTitle={(err as Error).message || '请刷新页面后重试'}
      />
    );
  }
}

bootstrap();
