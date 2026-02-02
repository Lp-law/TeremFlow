import { useNavigate } from 'react-router-dom'

export function BackButton() {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      onClick={() => navigate(-1)}
      className="btn btn-secondary"
    >
      חזרה למסך הקודם
    </button>
  )
}
