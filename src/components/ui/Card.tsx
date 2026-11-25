import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({ children, className = '', ...props }) => {
  return (
    <div
      className={`bg-[#121218] border border-[#1f1f2b] rounded-2xl p-5 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
