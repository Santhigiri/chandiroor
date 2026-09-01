from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import exc

from app.core.ports.unit_of_work import UnitOfWork

from app.core.security import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE, TokenError, decode_token, hash_password, verify_password
from app.features.auth.ports import AuthRepositoryPort, UserGet, UserNotFoundException, UserUpdate, UserCreate, UserWithCredentials
from app.features.auth.schemas import LoginUserRequest, GetUserResponse, CreateUserRequest, UpdateUserRequest
from panchangam_astronomy.enums.nakshatra import Nakshatra


class InvalidCredentailsException(Exception):
    pass

class UsernameTakenException(Exception):
    pass

class InvalidTokenException(Exception):
    pass


@dataclass(frozen=True)
class AuthService:
    auth_repository: AuthRepositoryPort
    uow: UnitOfWork


    def _user_get_to_get_user_response(self, user: UserGet) -> GetUserResponse: 
        return GetUserResponse(
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            email = user.email,
            full_name=user.full_name,
            date_of_birth=user.date_of_birth,
            birth_nakshatra= user.birth_nakshatra.name if user.birth_nakshatra else None
        )


    def login_user(self, user: LoginUserRequest) -> GetUserResponse:
        try:
            credentials = self.auth_repository.get_user_with_credentials(user.username)
        except UserNotFoundException:
            raise InvalidCredentailsException()
        if not credentials.is_active or not verify_password(user.password, credentials.hashed_password):
            raise InvalidCredentailsException()


        return self._user_get_to_get_user_response(credentials.to_user_get())


    def logout_user(self): 
        ...

    def create_user(self, user: CreateUserRequest) -> GetUserResponse:
        if self.auth_repository.exists(user.username):
            raise UsernameTakenException()

        with self.uow:
            new_user = self.auth_repository.create_user(
                UserCreate(
                    username= user.username,
                    hashed_password=hash_password(user.password),
                    role=user.role
                )
            )
            self.uow.commit()
            return self._user_get_to_get_user_response(new_user)



    def update_user(self, user: UpdateUserRequest, username: str) -> GetUserResponse:
        with self.uow as uow:
            selected_user = self.auth_repository.get_by_username(username)
            updated_user = self.auth_repository.update_user(
                UserUpdate(
                    username= selected_user.username,
                    is_active=selected_user.is_active,
                    role=selected_user.role,
                    full_name=user.full_name,
                    date_of_birth=user.date_of_birth,
                    birth_nakshatra=Nakshatra.get_or_none(user.birth_nakshatra)
                )
            )
            uow.commit()
            return self._user_get_to_get_user_response(updated_user)

    def get_user(self, username: str) -> GetUserResponse:
        user = self.auth_repository.get_by_username(username)
        return self._user_get_to_get_user_response(user)


        

    def _resolve_active_user(self, token: str, token_type: str)-> UserWithCredentials:
        try:
            claims = decode_token(token, token_type)
        except TokenError:
            raise InvalidTokenException()

        try:
            creds = self.auth_repository.get_user_with_credentials(claims["sub"])
        except UserNotFoundException:
            raise InvalidTokenException()

        if not creds.is_active:
            raise InvalidTokenException()

        return creds

    
    def refresh_session(self, refresh_token: str) -> UserGet:
        return self._resolve_active_user(refresh_token, REFRESH_TOKEN_TYPE).to_user_get()

    def resolve_principal_credentials(self, access_token: str)-> UserWithCredentials:
        return self._resolve_active_user(access_token, ACCESS_TOKEN_TYPE)



