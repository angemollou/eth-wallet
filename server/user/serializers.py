from rest_framework import serializers
from django.conf import settings
from django.contrib.auth import get_user_model
from djweb3.api import EthNode


class RegistrationSerializer(serializers.ModelSerializer):

    password2 = serializers.CharField(style={"input_type": "password"})
    is_new_wallet = serializers.BooleanField()

    class Meta:
        model = get_user_model()
        fields = (
            "first_name",
            "last_name",
            "email",
            "password",
            "password2",
            "is_new_wallet",
            "wallet_address_eth",
        )
        extra_kwargs = {
            "password": {"write_only": True},
            "password2": {"write_only": True},
            "is_new_wallet": {"write_only": True},
        }

    def save(self):
        user = get_user_model()(
            email=self.validated_data["email"],
            first_name=self.validated_data["first_name"],
            last_name=self.validated_data["last_name"],
            wallet_address_eth=self.validated_data.get("wallet_address_eth"),
        )

        password = self.validated_data["password"]
        password2 = self.validated_data["password2"]

        if password != password2:
            raise serializers.ValidationError({"password": "Passwords do not match!"})

        user.set_password(password)

        # on registration, create new wallet for user who ticks new wallet
        is_new_wallet = self.validated_data["is_new_wallet"]
        if user.wallet_address_eth is None and is_new_wallet in (1, True):
            node = EthNode()
            assert node.w3 is not None, "Failed to connect to Ethereum node unavailabe"
            account_eth = node.create_account()
            user.wallet_address_eth = account_eth.address
            user.private_key_eth = node.w3.to_hex(account_eth.key)
        user.save()

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)


class UserSerializer(serializers.ModelSerializer):
    balance_eth = serializers.SerializerMethodField("get_balance_eth")

    def get_balance_eth(self, obj):
        node = EthNode()
        return node.get_balance(obj.wallet_address_eth)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "is_staff",
            "first_name",
            "last_name",
            "wallet_address_eth",
            "balance_eth",
            "private_key_eth",
        )
