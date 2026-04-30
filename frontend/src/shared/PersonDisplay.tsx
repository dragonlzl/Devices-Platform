import { Avatar, Typography } from 'antd';
import { UserOutlined } from '@ant-design/icons';
import { getJobTitleText } from './auth';
import { PersonSnapshot } from './types';

type PersonDisplaySize = 'tiny' | 'small' | 'medium';

function getInitial(name: string) {
  const trimmed = name.trim();
  return trimmed ? trimmed.slice(0, 1) : undefined;
}

function cleanOptionalString(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

export function personFromBorrower(record: {
  borrower_name?: unknown;
  borrower_avatar_url?: unknown;
  borrower_job_title?: unknown;
}): PersonSnapshot | null {
  const name = String(record.borrower_name || '').trim();
  if (!name) {
    return null;
  }
  return {
    name,
    avatar_url: cleanOptionalString(record.borrower_avatar_url),
    job_title: cleanOptionalString(record.borrower_job_title),
  };
}

export function personFromChange(
  record: {
    borrower_before?: unknown;
    borrower_before_avatar_url?: unknown;
    borrower_before_job_title?: unknown;
    borrower_after?: unknown;
    borrower_after_avatar_url?: unknown;
    borrower_after_job_title?: unknown;
  },
  side: 'before' | 'after'
): PersonSnapshot | null {
  const nameKey = side === 'before' ? 'borrower_before' : 'borrower_after';
  const avatarKey = side === 'before' ? 'borrower_before_avatar_url' : 'borrower_after_avatar_url';
  const jobTitleKey = side === 'before' ? 'borrower_before_job_title' : 'borrower_after_job_title';
  const name = String(record[nameKey] || '').trim();
  if (!name) {
    return null;
  }
  return {
    name,
    avatar_url: cleanOptionalString(record[avatarKey]),
    job_title: cleanOptionalString(record[jobTitleKey]),
  };
}

export default function PersonDisplay(props: {
  person: PersonSnapshot | null | undefined;
  size?: PersonDisplaySize;
  showJobTitle?: boolean;
  fallback?: string;
  className?: string;
}) {
  const name = String(props.person?.name || '').trim();
  if (!name) {
    return <span className={props.className}>{props.fallback || '-'}</span>;
  }

  const size = props.size || 'small';
  const avatarSize = size === 'medium' ? 40 : size === 'small' ? 28 : 22;
  const jobTitle = props.showJobTitle ? getJobTitleText(props.person) : '';
  const initial = getInitial(name);
  const avatarUrl = cleanOptionalString(props.person?.avatar_url);
  const identityKey = [name, avatarUrl || '', jobTitle].join('|');

  return (
    <div className={`person-display person-display-${size} ${props.className || ''}`.trim()}>
      <Avatar
        key={identityKey}
        size={avatarSize}
        src={avatarUrl || undefined}
        icon={!avatarUrl && !initial ? <UserOutlined /> : undefined}
        className="person-display-avatar"
      >
        {!avatarUrl ? initial : null}
      </Avatar>
      <div className="person-display-text">
        <Typography.Text strong className="person-display-name" title={name}>
          {name}
        </Typography.Text>
        {props.showJobTitle ? (
          <Typography.Text className="person-display-job" title={jobTitle}>
            {jobTitle}
          </Typography.Text>
        ) : null}
      </div>
    </div>
  );
}
