import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, message } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
import 'antd/dist/reset.css';
import '../shared/styles.css';
import { appTheme } from '../shared/theme';
import AdminApp from './AdminApp';

message.config({ duration: 3 });
dayjs.locale('zh-cn');

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider theme={appTheme} locale={zhCN}>
      <AdminApp />
    </ConfigProvider>
  </React.StrictMode>
);
