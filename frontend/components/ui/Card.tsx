import React from "react";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = "",
  onClick,
}) => {
  return (
    <div
      onClick={onClick}
      className={`bg-surface rounded-2xl p-6 transition-shadow duration-200 hover:shadow-sm ${
        onClick ? "cursor-pointer" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
};
