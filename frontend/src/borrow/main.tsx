import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, message } from 'antd';
import 'antd/dist/reset.css';
import '../shared/styles.css';
import { appTheme } from '../shared/theme';
import BorrowApp from './BorrowApp';

message.config({ duration: 3 });

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider theme={appTheme}>
      <BorrowApp />
    </ConfigProvider>
  </React.StrictMode>
);
